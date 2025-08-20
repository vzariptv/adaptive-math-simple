#!/bin/bash

# Set environment variables for testing
export FLASK_ENV=testing
export TESTING=True

# Create a clean test database in the instance folder
test_db="instance/test_math_learning.db"
if [ -f "$test_db" ]; then
    rm "$test_db"
fi

# Run pytest
python -m pytest tests/ -v

# Clean up after tests
if [ -f "$test_db" ]; then
    rm "$test_db"
fi
