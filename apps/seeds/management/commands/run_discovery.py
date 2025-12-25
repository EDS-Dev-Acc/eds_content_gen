"""
Management command for running seed discovery from the CLI.

Phase 16: Provides a sync fallback when Celery is not available.

Usage:
    python manage.py run_discovery --theme "logistics companies" --geography "Vietnam"
    python manage.py run_discovery --theme "freight forwarders" --entity-types logistics_company freight_forwarder
    python manage.py run_discovery --help
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Run seed discovery with the specified target brief'
    
    def add_arguments(self, parser):
        # Required
        parser.add_argument(
            '--theme',
            type=str,
            required=True,
            help='Main theme/topic for discovery (e.g., "logistics companies")'
        )
        
        # Optional
        parser.add_argument(
            '--geography',
            type=str,
            default='',
            help='Comma-separated list of countries/regions (e.g., "Vietnam,Thailand")'
        )
        parser.add_argument(
            '--entity-types',
            nargs='+',
            default=[],
            help='Entity types to look for (e.g., logistics_company freight_forwarder)'
        )
        parser.add_argument(
            '--keywords',
            type=str,
            default='',
            help='Comma-separated additional keywords (e.g., "cargo,shipping")'
        )
        parser.add_argument(
            '--connectors',
            nargs='+',
            default=['html_directory', 'rss'],
            choices=['serp', 'rss', 'html_directory'],
            help='Connector types to use (default: html_directory rss)'
        )
        parser.add_argument(
            '--max-queries',
            type=int,
            default=20,
            help='Maximum number of queries to generate (default: 20)'
        )
        parser.add_argument(
            '--max-results',
            type=int,
            default=10,
            help='Maximum results per query (default: 10)'
        )
        parser.add_argument(
            '--seed-urls',
            nargs='+',
            default=[],
            help='Seed URLs to crawl for directory/RSS discovery'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Generate queries but do not execute discovery'
        )
        parser.add_argument(
            '--output-json',
            type=str,
            default='',
            help='Write results to JSON file'
        )
    
    def handle(self, *args, **options):
        from apps.seeds.discovery.query_generator import TargetBrief, QueryGenerator
        from apps.seeds.discovery.tasks import run_discovery_sync
        
        # Build target brief
        geography = [g.strip() for g in options['geography'].split(',') if g.strip()]
        keywords = [k.strip() for k in options['keywords'].split(',') if k.strip()]
        
        brief = TargetBrief(
            theme=options['theme'],
            entity_types=options['entity_types'],
            geography=geography,
            keywords=keywords,
        )
        
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Seed Discovery CLI'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(f"Theme: {brief.theme}")
        self.stdout.write(f"Geographies: {', '.join(geography) or '(none)'}")
        self.stdout.write(f"Entity Types: {', '.join(options['entity_types']) or '(none)'}")
        self.stdout.write(f"Keywords: {', '.join(keywords) or '(none)'}")
        self.stdout.write(f"Connectors: {', '.join(options['connectors'])}")
        self.stdout.write('')
        
        # Dry run: just show queries
        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('DRY RUN - Generating queries only'))
            self.stdout.write('')
            
            generator = QueryGenerator()
            queries = generator.generate(brief, max_queries=options['max_queries'])
            
            self.stdout.write(self.style.SUCCESS(f'Generated {len(queries)} queries:'))
            for i, q in enumerate(queries, 1):
                self.stdout.write(f"  {i}. [{q.query_type}] {q.query}")
                if q.country:
                    self.stdout.write(f"       Country: {q.country}")
            
            return
        
        # Full discovery run
        self.stdout.write(self.style.NOTICE('Starting discovery run...'))
        self.stdout.write('')
        
        try:
            result = run_discovery_sync(
                theme=options['theme'],
                geography=geography,
                entity_types=options['entity_types'],
                keywords=keywords,
                connectors=options['connectors'],
                max_queries=options['max_queries'],
                max_results_per_query=options['max_results'],
            )
            
            # Display results
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('Discovery Complete'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            
            if result:
                self.stdout.write(f"Run ID: {result.get('run_id', 'N/A')}")
                self.stdout.write(f"Status: {result.get('status', 'unknown')}")
                self.stdout.write(f"Queries executed: {result.get('queries_executed', 0)}")
                self.stdout.write(f"URLs discovered: {result.get('urls_discovered', 0)}")
                self.stdout.write(f"Seeds created: {result.get('seeds_created', 0)}")
                self.stdout.write(f"Duplicates skipped: {result.get('duplicates_skipped', 0)}")
                
                if result.get('errors'):
                    self.stdout.write(self.style.WARNING(f"Errors: {len(result['errors'])}"))
                    for err in result['errors'][:5]:
                        self.stdout.write(f"  - {err}")
                
                # Output JSON if requested
                if options['output_json']:
                    with open(options['output_json'], 'w') as f:
                        json.dump(result, f, indent=2, default=str)
                    self.stdout.write(f"\nResults written to: {options['output_json']}")
            else:
                self.stdout.write(self.style.WARNING('No results returned'))
            
        except Exception as e:
            raise CommandError(f'Discovery failed: {e}')
