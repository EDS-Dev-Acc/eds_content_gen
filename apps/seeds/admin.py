from django.contrib import admin
from django.utils.html import mark_safe
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django import forms
from urllib.parse import urlparse
import uuid
from .models import Seed, SeedRawCapture, SeedBatch


class BulkSeedImportForm(forms.Form):
    """Form for bulk importing seeds."""
    urls = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 20, 'cols': 80, 'placeholder': 'Enter one URL per line...'}),
        help_text='Enter one URL per line. URLs will be validated and deduplicated.'
    )
    seed_type = forms.ChoiceField(
        choices=Seed.SEED_TYPE_CHOICES,
        initial='unknown',
        required=False,
        help_text='Type to assign to all imported seeds'
    )
    country = forms.CharField(
        max_length=2,
        required=False,
        help_text='2-letter country code (e.g., US, UK)'
    )


@admin.register(Seed)
class SeedAdmin(admin.ModelAdmin):
    """Admin configuration for Seed model."""
    
    list_display = [
        'url_truncated',
        'domain',
        'seed_type',
        'status',
        'status_badge',
        'confidence',
        'country',
        'discovered_from_source',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'seed_type',
        'country',
        'is_reachable',
        'is_crawlable',
        'created_at',
    ]
    
    search_fields = [
        'url',
        'domain',
        'normalized_url',
    ]
    
    readonly_fields = [
        'id',
        'normalized_url',
        'domain',
        'validated_at',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('URL Information', {
            'fields': ('url', 'normalized_url', 'domain')
        }),
        ('Classification', {
            'fields': ('seed_type', 'confidence', 'country', 'regions', 'topics')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Validation Results', {
            'fields': ('is_reachable', 'is_crawlable', 'robots_unknown', 'has_articles', 
                      'article_count_estimate', 'validation_errors', 'validated_at')
        }),
        ('Discovery', {
            'fields': ('discovered_from_source', 'discovered_from_run', 'query_used', 
                      'referrer_url', 'discovery_run_id')
        }),
        ('Promotion', {
            'fields': ('promoted_to', 'promoted_by', 'promoted_at')
        }),
        ('Review', {
            'fields': ('review_status', 'reviewed_by', 'reviewed_at', 'review_notes', 'notes')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    change_list_template = 'admin/seeds/seed/change_list.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-import/', self.admin_site.admin_view(self.bulk_import_view), name='seeds_seed_bulk_import'),
        ]
        return custom_urls + urls
    
    def bulk_import_view(self, request):
        """Handle bulk seed import."""
        if request.method == 'POST':
            form = BulkSeedImportForm(request.POST)
            if form.is_valid():
                urls_text = form.cleaned_data['urls']
                seed_type = form.cleaned_data.get('seed_type', 'unknown')
                country = form.cleaned_data.get('country', '')
                
                # Parse URLs
                urls = [line.strip() for line in urls_text.splitlines() if line.strip()]
                
                # Create batch
                batch = SeedBatch.objects.create(
                    name=f'Admin Import - {len(urls)} URLs',
                    import_source='text',
                    total_count=len(urls),
                    imported_by=request.user,
                )
                
                created_count = 0
                duplicate_count = 0
                error_count = 0
                errors = []
                
                for url in urls:
                    # Basic URL validation
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    try:
                        parsed = urlparse(url)
                        if not parsed.netloc:
                            errors.append(f'Invalid URL: {url}')
                            error_count += 1
                            continue
                        
                        domain = parsed.netloc.lower()
                        if domain.startswith('www.'):
                            domain = domain[4:]
                        
                        # Check for duplicates
                        if Seed.objects.filter(url=url).exists():
                            duplicate_count += 1
                            continue
                        
                        # Create seed
                        Seed.objects.create(
                            url=url,
                            domain=domain,
                            normalized_url=url.lower().rstrip('/'),
                            seed_type=seed_type or 'unknown',
                            country=country.upper() if country else '',
                            status='pending',
                            import_source='text',
                            import_batch_id=batch.id,
                            added_by=request.user,
                        )
                        created_count += 1
                        
                    except Exception as e:
                        errors.append(f'{url}: {str(e)}')
                        error_count += 1
                
                # Update batch stats
                batch.success_count = created_count
                batch.duplicate_count = duplicate_count
                batch.error_count = error_count
                batch.errors = errors
                batch.save()
                
                messages.success(
                    request, 
                    f'Imported {created_count} seeds. Duplicates: {duplicate_count}. Errors: {error_count}.'
                )
                return redirect('admin:seeds_seed_changelist')
        else:
            form = BulkSeedImportForm()
        
        context = {
            'form': form,
            'title': 'Bulk Import Seeds',
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        return render(request, 'admin/seeds/seed/bulk_import.html', context)
    
    def url_truncated(self, obj):
        """Display truncated URL."""
        if len(obj.url) > 60:
            return obj.url[:60] + '...'
        return obj.url
    url_truncated.short_description = 'URL'
    
    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'gray',
            'validating': 'blue',
            'valid': 'green',
            'invalid': 'red',
            'promoted': 'purple',
            'rejected': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{obj.get_status_display()}</span>'
        )
    status_badge.short_description = 'Status'


@admin.register(SeedRawCapture)
class SeedRawCaptureAdmin(admin.ModelAdmin):
    """Admin configuration for SeedRawCapture model."""
    
    list_display = [
        'url',
        'status_code',
        'content_type',
        'created_at',
    ]
    
    list_filter = [
        'status_code',
        'content_type',
        'created_at',
    ]
    
    search_fields = [
        'url',
        'final_url',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]


@admin.register(SeedBatch)
class SeedBatchAdmin(admin.ModelAdmin):
    """Admin configuration for SeedBatch model."""
    
    list_display = [
        'name',
        'import_source',
        'total_count',
        'success_count',
        'duplicate_count',
        'error_count',
        'imported_by',
        'created_at',
    ]
    
    list_filter = [
        'import_source',
        'created_at',
    ]
    
    search_fields = [
        'name',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
