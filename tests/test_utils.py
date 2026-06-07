from nxbak.utils import mask_secret


def test_mask_secret():
    assert mask_secret("postgresql://password-token") == "post...oken"
    assert mask_secret("short") == "***"
    assert mask_secret(None) == "<unset>"
