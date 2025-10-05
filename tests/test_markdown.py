from highlights.markdown import sanitise_filename


def test_sanitise_filename_preserves_spaces():
    assert sanitise_filename("My Book Title") == "My Book Title"


def test_sanitise_filename_collapses_illegal_characters_to_spaces():
    assert sanitise_filename("My:/\\Book?Title*") == "My Book Title"


def test_sanitise_filename_returns_untitled_when_empty():
    assert sanitise_filename("@#$") == "untitled"
