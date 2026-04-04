from ai_multi_agent.core.config import Settings


def test_settings_accepts_ark_model_alias() -> None:
    settings = Settings(ARK_MODEL="mimo-v2-pro")

    assert settings.ark_model == "mimo-v2-pro"


def test_settings_accepts_legacy_doubao_model_alias() -> None:
    settings = Settings(DOUBAO_MODEL="legacy-model")

    assert settings.ark_model == "legacy-model"
    assert settings.doubao_model == "legacy-model"
