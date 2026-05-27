from my_coding_team.cli import main, run_doctor


def test_cli_help(capsys):
    exit_code = main(["--help"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "doctor" in output
    assert "my-coding-team" in output


def test_cli_config(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["config"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "model_provider" in output
    assert str(tmp_path) in output


def test_doctor_outputs_status(capsys, tmp_path):
    exit_code = run_doctor()
    output = capsys.readouterr().out

    assert exit_code in {0, 1}
    assert "My Coding Team doctor" in output
    assert "python:" in output
    assert "pydantic:" in output
    assert "agentscope:" in output
