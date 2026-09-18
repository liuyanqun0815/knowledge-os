from akos.application.ingest.subject_bind import bind_generic_subject, effective_subject_bind_mode, subject_bind_mode_override


def test_bind_generic_subject_rewrites_product_deixis():
    anchor = "青银理财成就系列（低波共享）"
    assert bind_generic_subject("本产品", anchor) == anchor
    assert bind_generic_subject("本理财计划", anchor) == anchor
    assert bind_generic_subject("本理财产品", anchor) == anchor


def test_bind_generic_subject_rewrites_roles_and_prefixed_roles():
    anchor = "青银理财成就系列（低波共享）"
    assert bind_generic_subject("投资者", anchor) == f"{anchor}的投资者"
    assert bind_generic_subject("本理财产品托管人", anchor) == f"{anchor}的托管人"
    assert bind_generic_subject("本产品管理人", anchor) == f"{anchor}的管理人"


def test_bind_generic_subject_keeps_concrete_names():
    anchor = "青银理财成就系列（低波共享）"
    assert bind_generic_subject("个人信用贷款", anchor) == "个人信用贷款"
    assert bind_generic_subject("青银理财有限责任公司", anchor) == "青银理财有限责任公司"
    assert bind_generic_subject(f"{anchor}的投资者", anchor) == f"{anchor}的投资者"


def test_subject_bind_mode_override_context():
    assert effective_subject_bind_mode("auto") == "auto"
    with subject_bind_mode_override("off"):
        assert effective_subject_bind_mode("auto") == "off"
    assert effective_subject_bind_mode("auto") == "auto"
