#!/usr/bin/env python3
"""
Example usage of the utils module.
"""

from scribe import (
    normalize_path,
    sanitize_filename,
    generate_file_id,
    SimpleWorkerPool,
    ProgressTracker,
    chunk_list
)


def process_file_batch_example():
    """Example of processing files in parallel."""
    
    # Example file paths with various naming issues
    file_paths = [
        "data/Interview_2024.mp3",
        "data/Müller Interview.mp4",
        "data/עברית_ראיון.mp3",  # Hebrew filename
        "data/file with   spaces.wav",
        "data/Special!@#$%^Characters.mp3"
    ]
    
    print("Processing file batch example:\n")
    
    # Sanitize filenames
    print("1. Sanitizing filenames:")
    sanitized_files = []
    for path in file_paths:
        original_name = path.split('/')[-1]
        safe_name = sanitize_filename(original_name)
        file_id = generate_file_id()
        sanitized_files.append({
            'id': file_id,
            'original': path,
            'safe_name': safe_name
        })
        print(f"   {original_name} -> {safe_name} (ID: {file_id[:8]}...)")
    
    print("\n2. Processing files in parallel:")
    
    def process_file(file_info):
        """Simulate processing a file."""
        import time
        import random
        
        # Simulate some work
        time.sleep(random.uniform(0.1, 0.3))
        
        # Simulate success/failure
        if random.random() > 0.8:  # 20% failure rate
            raise Exception(f"Failed to process {file_info['safe_name']}")
        
        return f"Processed {file_info['safe_name']}"
    
    # Process with worker pool
    with SimpleWorkerPool(max_workers=3) as pool:
        # Use progress tracker
        tracker = ProgressTracker(len(sanitized_files), "Processing files")
        
        def callback(item, result, error):
            tracker.update(success=(error is None))
            if error:
                print(f"   ✗ {item['safe_name']}: {error}")
            else:
                print(f"   ✓ {item['safe_name']}: {result}")
        
        stats = pool.process_batch(process_file, sanitized_files, callback=callback)
    
    print(f"\n3. Processing complete:")
    print(f"   Total: {stats['total']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Failed: {stats['failed']}")


def batch_processing_example():
    """Example of chunking for batch processing."""
    
    print("\nBatch processing example:\n")
    
    # Large list of items to process
    items = list(range(100))
    
    # Split into chunks for batch processing
    batch_size = 20
    chunks = chunk_list(items, batch_size)
    
    print(f"Processing {len(items)} items in {len(chunks)} batches of {batch_size}")
    
    # Process each chunk
    for i, chunk in enumerate(chunks):
        print(f"  Batch {i+1}: Processing items {chunk[0]} to {chunk[-1]}")


def path_handling_example():
    """Example of path handling with Unicode."""
    
    print("\nPath handling example:\n")
    
    test_paths = [
        "data/interviews/Müller_2024.mp3",
        "data/interviews/../archive/old_interview.mp4",
        "data/interviews/שלום עולם.mp3",  # Hebrew
        "data/interviews/José García.wav"  # Spanish
    ]
    
    print("Normalizing paths:")
    for path in test_paths:
        normalized = normalize_path(path)
        print(f"  {path}")
        print(f"  -> {normalized}\n")


if __name__ == "__main__":
    print("Scribe Utils Examples")
    print("=" * 50)
    
    process_file_batch_example()
    print("\n" + "=" * 50)
    
    batch_processing_example()
    print("\n" + "=" * 50)
    
    path_handling_example()