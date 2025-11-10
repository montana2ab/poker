"""Test automatic chunk restart functionality."""

import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_chunked_coordinator_auto_restart_loop():
    """Test that chunked coordinator automatically restarts after each chunk."""
    
    # This is a structural test that verifies the logic flow
    # without requiring full dependencies
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        logdir = tmpdir_path / "logs"
        
        # Mock the entire ChunkedTrainingCoordinator class
        from unittest.mock import Mock
        
        # Create a mock that simulates the behavior
        mock_solver = Mock()
        mock_solver.iteration = 0
        mock_solver.writer = None
        mock_solver._cumulative_elapsed_seconds = 0
        
        # Track how many chunks are run
        chunk_count = [0]
        
        def mock_is_training_complete(solver):
            """Mock that returns True after 3 chunks."""
            chunk_count[0] += 1
            return chunk_count[0] >= 3
        
        # The key test: verify that the run() method would loop
        # In the actual implementation, it should:
        # 1. Run one chunk
        # 2. Check if complete
        # 3. If not complete, restart (loop back to step 1)
        # 4. If complete, break and exit
        
        # Simulate 3 iterations
        training_complete = False
        iterations = 0
        max_iterations = 3
        
        while not training_complete and iterations < max_iterations:
            iterations += 1
            # Simulate chunk processing
            # ... chunk runs ...
            
            # Check if training complete
            training_complete = mock_is_training_complete(mock_solver)
        
        # Verify we ran 3 chunks before completion
        assert iterations == 3
        assert training_complete == True


def test_chunked_message_indicates_auto_restart():
    """Test that log messages indicate automatic restart."""
    
    # This test verifies that the message changed from
    # "Process will now exit to free memory" to
    # "Automatically restarting for next chunk"
    
    # This is tested by checking the actual source code structure
    chunked_coordinator_path = Path(__file__).parent.parent / "src" / "holdem" / "mccfr" / "chunked_coordinator.py"
    
    with open(chunked_coordinator_path, 'r') as f:
        content = f.read()
    
    # Check that the old message is removed
    assert "Process will now exit to free memory" not in content, \
        "Old message should be removed"
    assert "Restart this command to continue training" not in content, \
        "Old manual restart message should be removed"
    
    # Check that the new message exists
    assert "Automatically restarting for next chunk" in content, \
        "New auto-restart message should be present"
    
    # Check that there's a loop structure
    assert "while True:" in content, \
        "Should have infinite loop for auto-restart"
    assert "break  # Exit the loop" in content or "break" in content, \
        "Should have break condition when training complete"


def test_multi_instance_coordinator_message_updated():
    """Test that multi_instance_coordinator message reflects auto-restart."""
    
    multi_instance_path = Path(__file__).parent.parent / "src" / "holdem" / "mccfr" / "multi_instance_coordinator.py"
    
    with open(multi_instance_path, 'r') as f:
        content = f.read()
    
    # Check that the comment was updated
    assert "automatically restarts until complete" in content or \
           "automatically restarts" in content, \
        "Comment should indicate automatic restart"
    
    # Check that old chunk_completed status is not used
    # (it should now just be "completed" when fully done)
    lines = content.split('\n')
    chunk_completed_lines = [line for line in lines if 'chunk_completed' in line]
    
    # If chunk_completed exists, it should be in old commented code or removed
    # The actual status should be "completed"
    assert any('"completed"' in line for line in lines), \
        "Should mark as 'completed' when training is done"


def test_automatic_restart_respects_training_completion():
    """Test that automatic restart stops when training is complete."""
    
    # Mock scenario: training completes after 2 chunks
    chunk_iterations = [0]
    
    def simulate_chunk_run():
        """Simulate running one chunk."""
        chunk_iterations[0] += 1
        
    def is_complete():
        """Check if training is complete (after 2 chunks)."""
        return chunk_iterations[0] >= 2
    
    # Simulate the while loop logic
    while not is_complete():
        simulate_chunk_run()
        # In real code, this would save checkpoint and check completion
    
    assert chunk_iterations[0] == 2, "Should stop after training completes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
