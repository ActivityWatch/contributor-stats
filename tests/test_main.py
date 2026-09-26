from contributor_stats.main import (
    author_aliases,
    get_authorInfos,
    group_names_by_email,
    merge_emails,
    normalize_email,
    normalize_name,
)


class FakeData:
    """Stands in for gitstats.GitDataCollector, which needs an actual repo."""

    def __init__(self, authors):
        self.authors = authors

    def getAuthors(self):
        return list(self.authors)

    def getAuthorInfo(self, author):
        return dict(self.authors[author])


def author(commits, active_days, lines_added=0, lines_removed=0):
    return dict(
        commits=commits,
        active_days=active_days,
        lines_added=lines_added,
        lines_removed=lines_removed,
    )


def test_normalize_name():
    # NFD and NFC spellings of the same name are the same author
    assert normalize_name("Måns") == normalize_name("Måns")


def test_normalize_email():
    assert normalize_email(" Erik@Bjareho.lt ") == "erik@bjareho.lt"
    # Not usable to identify an author
    assert normalize_email("not an email") == ""
    assert normalize_email("noreply@github.com") == ""


def test_group_names_by_email():
    groups = group_names_by_email(
        {
            "Brayo": {"vukubrian@gmail.com": 2, "brayo@laptop.local": 1},
            "brayo": {"vukubrian@gmail.com": 1},
            "Erik": {"erik@bjareho.lt": 1},
        }
    )
    assert sorted(sorted(group) for group in groups) == [["Brayo", "brayo"], ["Erik"]]


def test_group_names_by_email_is_transitive():
    groups = group_names_by_email(
        {
            "a": {"one@example.com": 1},
            "b": {"one@example.com": 1, "two@example.com": 1},
            "c": {"two@example.com": 1},
        }
    )
    assert [sorted(group) for group in groups] == [["a", "b", "c"]]


def test_author_aliases_picks_the_name_with_most_commits():
    aliases = author_aliases(
        {"Brayo": {"vukubrian@gmail.com": 5}, "brayo": {"vukubrian@gmail.com": 1}}
    )
    assert aliases == {"brayo": "Brayo"}


def test_author_aliases_ties_are_deterministic():
    emails = {"Brayo": {"vukubrian@gmail.com": 1}, "brayo": {"vukubrian@gmail.com": 1}}
    assert author_aliases(emails) == {"brayo": "Brayo"}
    assert author_aliases(dict(reversed(list(emails.items())))) == {"brayo": "Brayo"}


def test_author_aliases_keeps_authors_without_a_shared_email_apart():
    assert author_aliases(
        {"Brayo": {"vukubrian@gmail.com": 1}, "Erik": {"erik@bjareho.lt": 1}}
    ) == {}


def test_merge_emails():
    merged = merge_emails(
        [
            {"Brayo": {"vukubrian@gmail.com": 2}},
            {"Brayo": {"vukubrian@gmail.com": 3}, "brayo": {"vukubrian@gmail.com": 1}},
        ]
    )
    assert merged == {
        "Brayo": {"vukubrian@gmail.com": 5},
        "brayo": {"vukubrian@gmail.com": 1},
    }


def test_get_authorInfos_merges_aliases():
    data = FakeData(
        {
            "Brayo": author(commits=2, active_days=["2025-01-01", "2025-01-02"], lines_added=10),
            "brayo": author(commits=1, active_days=["2025-01-02"], lines_added=5),
            "Erik": author(commits=1, active_days=["2025-01-03"], lines_added=1),
        }
    )
    authorInfos, merged_into = get_authorInfos(data, {"brayo": "Brayo"})

    assert set(authorInfos) == {"Brayo", "Erik"}
    assert authorInfos["Brayo"]["commits"] == 3
    assert authorInfos["Brayo"]["lines_added"] == 15
    assert authorInfos["Brayo"]["active_days"] == {"2025-01-01", "2025-01-02"}
    # so that blame lines of an alias are attributed to the merged author
    assert merged_into["brayo"] == "Brayo"
    assert merged_into["Brayo"] == "Brayo"


def test_get_authorInfos_merges_into_a_name_not_in_the_repo():
    data = FakeData({"brayo": author(commits=1, active_days=["2025-01-01"])})
    authorInfos, merged_into = get_authorInfos(data, {"brayo": "Brayo"})

    assert set(authorInfos) == {"Brayo"}
    assert authorInfos["Brayo"]["commits"] == 1
    assert merged_into["brayo"] == "Brayo"


def test_get_authorInfos_still_applies_the_manual_merges():
    # These aliases don't share a commit email, so they need the manual list
    data = FakeData(
        {
            "dependabot[bot]": author(commits=1, active_days=["2025-01-01"]),
            "dependabot-preview[bot]": author(commits=2, active_days=["2025-01-02"]),
        }
    )
    authorInfos, merged_into = get_authorInfos(data)

    assert set(authorInfos) == {"dependabot[bot]"}
    assert authorInfos["dependabot[bot]"]["commits"] == 3
    assert merged_into["dependabot-preview[bot]"] == "dependabot[bot]"


def test_get_authorInfos_merges_names_that_normalize_to_the_same_one():
    data = FakeData(
        {
            "Måns": author(commits=1, active_days=["2025-01-01"]),
            "Måns": author(commits=2, active_days=["2025-01-02"]),
        }
    )
    authorInfos, _ = get_authorInfos(data)

    assert len(authorInfos) == 1
    assert list(authorInfos.values())[0]["commits"] == 3
