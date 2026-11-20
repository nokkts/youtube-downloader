import pytest

from app.utils.validators import (RangeError, TimeRange, format_timecode, normalize_youtube_url, parse_timecode,
                                  validate_range)

ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={ID}", f"https://youtu.be/{ID}", f"youtu.be/{ID}?t=30",
    f"https://youtube.com/shorts/{ID}?feature=share", f"https://m.youtube.com/watch?v={ID}&list=PLx&index=2",
    f"https://www.youtube.com/live/{ID}", f"  https://www.youtube.com/watch?v={ID}  ",
])
def test_valid_urls(url):
    assert normalize_youtube_url(url) == f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize("url", ["", "abc", "https://evil.com/watch?v=" + ID, "https://youtube.com/watch?v=curto",
                                 "https://youtube.com/playlist?list=PLabc", "https://vimeo.com/123", "ftp://"])
def test_invalid_urls(url):
    assert normalize_youtube_url(url) is None


@pytest.mark.parametrize("txt,val", [("05:30", 330), ("1:02:03", 3723), ("90", 90), ("00:00:12.5", 12.5), ("0", 0)])
def test_parse_ok(txt, val):
    assert parse_timecode(txt) == val


@pytest.mark.parametrize("txt", ["", "abc", "1:75", "1:61:00", "1:2:3:4", "-5", "00:-1"])
def test_parse_bad(txt):
    assert parse_timecode(txt) is None


def test_format():
    assert format_timecode(330) == "00:05:30"
    assert format_timecode(3723.5, with_ms=True) == "01:02:03.500"


def test_range_example_from_spec():
    r = validate_range("05:30", "12:45", 2400)
    assert r == TimeRange(330, 765) and r.length == 435


def test_range_full_video_when_empty():
    assert validate_range("", "", 2400) is None
    assert validate_range("00:00:00", "", 2400) is None
    assert validate_range("0", "00:40:00", 2400) is None  # equivale ao vídeo inteiro


def test_range_end_defaults_to_duration():
    assert validate_range("10:00", "", 2400) == TimeRange(600, 2400)


@pytest.mark.parametrize("s,e,msg", [
    ("10:00", "05:00", "anterior"), ("05:00", "05:00", "anterior"), ("-1", "10", "negativo"), ("00:01", "-10", "negativo"),
    ("41:00", "42:00", "ultrapassa"), ("10:00", "50:00", "ultrapassa"), ("xx", "10:00", "Início inválido"),
    ("00:10", "yy", "Fim inválido"),
])
def test_range_errors(s, e, msg):
    with pytest.raises(RangeError, match=msg):
        validate_range(s, e, 2400)
