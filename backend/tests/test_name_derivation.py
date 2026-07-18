from app.greeting import derive_first_name


def test_multi_part_name():
    assert derive_first_name("PRITAM NITIN WAVHAL") == "Pritam"


def test_single_name():
    assert derive_first_name("PRITAM") == "Pritam"


def test_extra_whitespace():
    assert derive_first_name("  PRITAM   NITIN ") == "Pritam"


def test_empty_name_is_none():
    assert derive_first_name("") is None


def test_whitespace_only_is_none():
    assert derive_first_name("   ") is None


def test_missing_name_is_none():
    assert derive_first_name(None) is None


def test_non_string_is_none():
    assert derive_first_name(12345) is None
