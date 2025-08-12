from release_copilot.kit.jira_key import extract_keys


def test_extract_keys_multiple():
    text = "Fix MOB-123 and MOB-456 in this commit"
    assert set(extract_keys(text)) == {"MOB-123", "MOB-456"}


def test_extract_keys_none():
    assert extract_keys("no key here") == []
