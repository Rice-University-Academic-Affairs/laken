from pathlib import Path

from laken.deploy.build import clean_dist, run_build


def test_clean_dist_removes_existing_dist(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "old.whl").write_text("")
    monkeypatch.chdir(tmp_path)

    clean_dist()

    assert not dist.exists()


def test_run_build_cleans_dist_before_uv_build(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "old.whl").write_text("")
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_run(args, cwd, check):
        calls.append((args, cwd, check, dist.exists()))

    monkeypatch.setattr("laken.deploy.build.subprocess.run", fake_run)

    run_build()

    assert calls == [(["uv", "build"], Path.cwd(), True, False)]
