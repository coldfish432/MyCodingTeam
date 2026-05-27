import my_coding_team
from my_coding_team.config import load_config


def test_package_imports():
    assert my_coding_team.__version__


def test_config_defaults_are_local(tmp_path):
    config = load_config(env={}, cwd=tmp_path)

    assert config.model_provider is None
    assert config.model_name is None
    assert config.default_workspace == str(tmp_path)
    assert config.log_dir == str(tmp_path / ".my_coding_team" / "logs")
