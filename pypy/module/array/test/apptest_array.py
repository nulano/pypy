# spaceconfig = {"usemodules": ["array"]}
import pytest
from array import array

def test_index_positions():
    a = array('i', [1, 2, 3, 1, 2, 1])
    assert a.index(1, start=2) == 3
    with pytest.raises(ValueError):
        a.index(1, start=1, stop=3)
