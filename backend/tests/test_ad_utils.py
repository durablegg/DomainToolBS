from app.services import ad_group, ad_utils


def test_decode_uac():
    assert ad_utils.decode_uac(512)["enabled"] is True
    assert ad_utils.decode_uac(514)["enabled"] is False
    assert ad_utils.decode_uac(66048)["pwd_never_expires"] is True
    assert ad_utils.decode_uac(0x12)["locked"] is True  # 0x10 LOCKOUT


def test_filetime_to_dt():
    assert ad_utils.filetime_to_dt(0) is None
    assert ad_utils.filetime_to_dt(0x7FFFFFFFFFFFFFFF) is None
    dt = ad_utils.filetime_to_dt(133000000000000000)
    assert dt is not None and dt.year == 2022


def test_set_uac_flag():
    # 开启 ACCOUNT_DISABLE(0x2) 后再关闭
    uac = ad_utils.set_uac_flag(512, ad_utils.UAC_ACCOUNT_DISABLE, True)
    assert uac & ad_utils.UAC_ACCOUNT_DISABLE
    uac2 = ad_utils.set_uac_flag(uac, ad_utils.UAC_ACCOUNT_DISABLE, False)
    assert not (uac2 & ad_utils.UAC_ACCOUNT_DISABLE)


def test_group_type():
    assert ad_group.scope_to_grouptype("global", True) == 0x80000002
    assert ad_group.is_security(0x80000002) is True
    assert ad_group.is_security(2) is False
    assert ad_group.scope_to_grouptype("global", False) == 2
