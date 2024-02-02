# tests/test_application.py

import pytest
from pitop import main

def test_application_starts():
    assert main(testing=True)  
