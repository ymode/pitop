# test_application.py

import pytest
from pitop import main  # Replace with the actual import

def test_application_starts():
    try:
        main()  # Replace with the actual function that starts your application
    except Exception as e:
        pytest.fail(f"Application failed to start: {e}")
