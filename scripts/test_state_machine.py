#!/usr/bin/env python
"""
Test script for Phase 6: Article Processing State Machine.

Tests:
1. ArticleState enum and transitions
2. ArticleStateMachine basic operations
3. State transition hooks
4. Error handling and retry logic
5. ProcessingPipeline
6. StateMachineProcessor integration
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.articles.state_machine import (
    ArticleState,
    ArticleStateMachine,
    TransitionError,
    TransitionContext,
    StateTransition,
    ProcessingPipeline,
    VALID_TRANSITIONS,
    with_state_machine,
)
from apps.articles.models import Article
from apps.sources.models import Source


def get_or_create_test_source():
    """Get or create a test source."""
    source, _ = Source.objects.get_or_create(
        domain='statemachine-test.com',
        defaults={
            'name': 'State Machine Test Source',
            'url': 'https://statemachine-test.com',
            'crawler_type': 'modular',
            'status': 'active',
        }
    )
    return source


def create_test_article(status='collected'):
    """Create a test article."""
    source = get_or_create_test_source()
    article = Article.objects.create(
        source=source,
        url=f'https://statemachine-test.com/article-{Article.objects.count() + 1}',
        title='Test Article for State Machine',
        processing_status=status,
    )
    return article


def test_article_state_enum():
    """Test ArticleState enum values and properties."""
    print("\n=== Test 1: ArticleState Enum ===")
    
    # Test all expected states exist
    expected = ['collected', 'extracting', 'extracted', 'translating', 
                'translated', 'scoring', 'scored', 'completed', 'failed']
    
    for state_value in expected:
        state = ArticleState.from_string(state_value)
        assert state.value == state_value
    print(f"✓ All {len(expected)} states defined correctly")
    
    # Test terminal states
    assert ArticleState.COMPLETED.is_terminal
    assert ArticleState.FAILED.is_terminal
    assert not ArticleState.EXTRACTED.is_terminal
    print("✓ Terminal states identified correctly")
    
    # Test processing states
    assert ArticleState.EXTRACTING.is_processing
    assert ArticleState.TRANSLATING.is_processing
    assert ArticleState.SCORING.is_processing
    assert not ArticleState.EXTRACTED.is_processing
    print("✓ Processing states identified correctly")
    
    return True


def test_valid_transitions():
    """Test that valid transitions are correctly defined."""
    print("\n=== Test 2: Valid Transitions ===")
    
    # Test COLLECTED can go to EXTRACTING
    assert ArticleState.EXTRACTING in VALID_TRANSITIONS[ArticleState.COLLECTED]
    print("✓ COLLECTED → EXTRACTING is valid")
    
    # Test EXTRACTED can go to TRANSLATING or SCORING
    assert ArticleState.TRANSLATING in VALID_TRANSITIONS[ArticleState.EXTRACTED]
    assert ArticleState.SCORING in VALID_TRANSITIONS[ArticleState.EXTRACTED]
    print("✓ EXTRACTED → TRANSLATING or SCORING is valid")
    
    # Test any state can fail
    for state in ArticleState:
        if state not in (ArticleState.COMPLETED, ArticleState.FAILED):
            assert ArticleState.FAILED in VALID_TRANSITIONS.get(state, set())
    print("✓ All non-terminal states can transition to FAILED")
    
    # Test FAILED can retry to COLLECTED
    assert ArticleState.COLLECTED in VALID_TRANSITIONS[ArticleState.FAILED]
    print("✓ FAILED → COLLECTED (retry) is valid")
    
    # Test COMPLETED is terminal
    assert len(VALID_TRANSITIONS[ArticleState.COMPLETED]) == 0
    print("✓ COMPLETED is terminal (no outgoing transitions)")
    
    return True


def test_state_machine_basic():
    """Test ArticleStateMachine basic operations."""
    print("\n=== Test 3: ArticleStateMachine Basic ===")
    
    article = create_test_article(status='collected')
    machine = ArticleStateMachine(article)
    
    # Test current state
    assert machine.current_state == ArticleState.COLLECTED
    print(f"✓ Current state: {machine.current_state.value}")
    
    # Test valid transitions check
    assert machine.can_transition_to(ArticleState.EXTRACTING)
    assert not machine.can_transition_to(ArticleState.COMPLETED)
    print("✓ can_transition_to works correctly")
    
    # Test get_valid_transitions
    valid = machine.get_valid_transitions()
    assert ArticleState.EXTRACTING in valid
    assert ArticleState.FAILED in valid
    print(f"✓ Valid transitions: {[s.value for s in valid]}")
    
    # Test transition
    machine.transition_to(ArticleState.EXTRACTING)
    assert machine.current_state == ArticleState.EXTRACTING
    print("✓ Transition to EXTRACTING succeeded")
    
    # Verify article was updated
    article.refresh_from_db()
    assert article.processing_status == 'extracting'
    print("✓ Article status updated in database")
    
    # Test history
    assert len(machine.history) == 1
    assert machine.history[0].from_state == ArticleState.COLLECTED
    assert machine.history[0].to_state == ArticleState.EXTRACTING
    print("✓ Transition recorded in history")
    
    # Cleanup
    article.delete()
    
    return True


def test_invalid_transition():
    """Test that invalid transitions are rejected."""
    print("\n=== Test 4: Invalid Transition Handling ===")
    
    article = create_test_article(status='collected')
    machine = ArticleStateMachine(article)
    
    # Try invalid transition
    try:
        machine.transition_to(ArticleState.COMPLETED)
        assert False, "Should have raised TransitionError"
    except TransitionError as e:
        print(f"✓ Invalid transition rejected: {e}")
    
    # Verify state unchanged
    assert machine.current_state == ArticleState.COLLECTED
    print("✓ State unchanged after invalid transition")
    
    # Test force transition
    machine.transition_to(ArticleState.COMPLETED, force=True)
    assert machine.current_state == ArticleState.COMPLETED
    print("✓ Force transition succeeded")
    
    # Cleanup
    article.delete()
    
    return True


def test_fail_and_retry():
    """Test failure and retry mechanism."""
    print("\n=== Test 5: Fail and Retry ===")
    
    article = create_test_article(status='collected')
    machine = ArticleStateMachine(article, max_retries=3)
    
    # Transition to extracting
    machine.transition_to(ArticleState.EXTRACTING)
    
    # Fail
    machine.fail("Test error message")
    
    assert machine.current_state == ArticleState.FAILED
    print("✓ Transition to FAILED succeeded")
    
    # Check error was recorded
    article.refresh_from_db()
    assert article.processing_error == "Test error message"
    assert article.metadata.get('retry_count') == 1
    print("✓ Error and retry count recorded")
    
    # Retry
    success = machine.retry()
    assert success
    assert machine.current_state == ArticleState.COLLECTED
    print("✓ Retry succeeded, back to COLLECTED")
    
    # Exhaust retries - fail 3 more times
    for i in range(2):  # Need 2 more failures (already at retry_count=1)
        machine.transition_to(ArticleState.EXTRACTING)
        machine.fail(f"Error {i+2}")
        if machine.current_state == ArticleState.FAILED and machine.retry_count < machine.max_retries:
            machine.retry()
    
    # One more fail to hit max retries
    if machine.current_state == ArticleState.COLLECTED:
        machine.transition_to(ArticleState.EXTRACTING)
        machine.fail("Final error")
    
    # Should now be at max retries - retry should fail
    success = machine.retry()
    assert not success
    print(f"✓ Retry blocked after max retries (count={machine.retry_count})")
    
    # Cleanup
    article.delete()
    
    return True


def test_reset():
    """Test state machine reset."""
    print("\n=== Test 6: Reset ===")
    
    article = create_test_article(status='collected')
    machine = ArticleStateMachine(article)
    
    # Progress through several states
    machine.transition_to(ArticleState.EXTRACTING)
    machine.transition_to(ArticleState.EXTRACTED)
    machine.transition_to(ArticleState.SCORING)
    machine.fail("Error during scoring")
    
    # Record retry count
    article.refresh_from_db()
    assert machine.retry_count > 0
    
    # Reset
    machine.reset()
    
    article.refresh_from_db()
    assert machine.current_state == ArticleState.COLLECTED
    assert article.processing_error == ''
    assert article.metadata.get('retry_count') == 0
    print("✓ Reset cleared state, error, and retry count")
    
    # History should be cleared
    assert len(machine.history) == 0
    print("✓ History cleared")
    
    # Cleanup
    article.delete()
    
    return True


def test_hooks():
    """Test transition hooks."""
    print("\n=== Test 7: Transition Hooks ===")
    
    hook_calls = []
    
    def before_hook(ctx: TransitionContext):
        hook_calls.append(('before', ctx.from_state.value, ctx.to_state.value))
    
    def after_hook(ctx: TransitionContext):
        hook_calls.append(('after', ctx.from_state.value, ctx.to_state.value))
    
    article = create_test_article(status='collected')
    machine = ArticleStateMachine(article)
    
    # Register instance hooks
    machine.before(ArticleState.COLLECTED, ArticleState.EXTRACTING, before_hook)
    machine.after(ArticleState.COLLECTED, ArticleState.EXTRACTING, after_hook)
    
    # Make transition
    machine.transition_to(ArticleState.EXTRACTING)
    
    assert len(hook_calls) == 2
    assert hook_calls[0] == ('before', 'collected', 'extracting')
    assert hook_calls[1] == ('after', 'collected', 'extracting')
    print("✓ Before and after hooks called correctly")
    
    # Cleanup
    article.delete()
    
    return True


def test_processing_pipeline():
    """Test ProcessingPipeline."""
    print("\n=== Test 8: ProcessingPipeline ===")
    
    stage_calls = []
    
    def mock_extract(article):
        stage_calls.append('extract')
        article.extracted_text = "Test extracted text"
        article.save(update_fields=['extracted_text'])
    
    def mock_score(article):
        stage_calls.append('score')
        article.total_score = 75
        article.save(update_fields=['total_score'])
    
    article = create_test_article(status='collected')
    
    # Create pipeline
    pipeline = ProcessingPipeline()
    pipeline.add_stage(
        name='extract',
        func=mock_extract,
        start_state=ArticleState.EXTRACTING,
        end_state=ArticleState.EXTRACTED,
    )
    pipeline.add_stage(
        name='score',
        func=mock_score,
        start_state=ArticleState.SCORING,
        end_state=ArticleState.SCORED,
    )
    
    # Process
    success = pipeline.process(article)
    
    assert success
    print("✓ Pipeline processed successfully")
    
    assert stage_calls == ['extract', 'score']
    print(f"✓ Stages executed in order: {stage_calls}")
    
    article.refresh_from_db()
    assert article.processing_status == 'completed'
    print("✓ Final status is 'completed'")
    
    # Test current stage detection
    article2 = create_test_article(status='extracting')
    stage = pipeline.get_current_stage(article2)
    assert stage == 'extract'
    print(f"✓ Current stage detected: {stage}")
    
    # Cleanup
    article.delete()
    article2.delete()
    
    return True


def test_pipeline_skip_stage():
    """Test ProcessingPipeline skip condition."""
    print("\n=== Test 9: Pipeline Skip Condition ===")
    
    stage_calls = []
    
    def mock_translate(article):
        stage_calls.append('translate')
    
    def mock_score(article):
        stage_calls.append('score')
    
    article = create_test_article(status='extracted')
    article.extracted_text = "Some text"
    article.save()
    
    # Create pipeline with skip condition for translation
    pipeline = ProcessingPipeline()
    pipeline.add_stage(
        name='translate',
        func=mock_translate,
        start_state=ArticleState.TRANSLATING,
        end_state=ArticleState.TRANSLATED,
        skip_if=lambda a: True,  # Always skip
    )
    pipeline.add_stage(
        name='score',
        func=mock_score,
        start_state=ArticleState.SCORING,
        end_state=ArticleState.SCORED,
    )
    
    success = pipeline.process(article, start_from=ArticleState.TRANSLATING)
    
    assert success
    assert 'translate' not in stage_calls
    assert 'score' in stage_calls
    print("✓ Translation stage skipped, scoring executed")
    
    # Cleanup
    article.delete()
    
    return True


def test_with_state_machine_decorator():
    """Test the with_state_machine decorator."""
    print("\n=== Test 10: with_state_machine Decorator ===")
    
    @with_state_machine
    def process_article(article, machine):
        machine.transition_to(ArticleState.EXTRACTING)
        # Simulate work
        machine.transition_to(ArticleState.EXTRACTED)
        return article
    
    article = create_test_article(status='collected')
    
    result = process_article(article)
    
    result.refresh_from_db()
    assert result.processing_status == 'extracted'
    print("✓ Decorator managed state transitions")
    
    # Test error handling
    @with_state_machine
    def failing_process(article, machine):
        machine.transition_to(ArticleState.EXTRACTING)
        raise ValueError("Simulated error")
    
    article2 = create_test_article(status='collected')
    
    try:
        failing_process(article2)
    except ValueError:
        pass
    
    article2.refresh_from_db()
    assert article2.processing_status == 'failed'
    assert 'Simulated error' in article2.processing_error
    print("✓ Decorator caught error and transitioned to FAILED")
    
    # Cleanup
    article.delete()
    article2.delete()
    
    return True


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_article_state_enum,
        test_valid_transitions,
        test_state_machine_basic,
        test_invalid_transition,
        test_fail_and_retry,
        test_reset,
        test_hooks,
        test_processing_pipeline,
        test_pipeline_skip_stage,
        test_with_state_machine_decorator,
    ]
    
    print("=" * 60)
    print("Phase 6: Article Processing State Machine Tests")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} returned False")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All Phase 6 tests passed!")
        return True
    else:
        print(f"\n✗ {failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
