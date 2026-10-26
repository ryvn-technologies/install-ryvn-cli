from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ACTION = yaml.safe_load((Path(__file__).resolve().parents[1] / "action.yml").read_text())


class InstallTest(unittest.TestCase):
    def test_installer_environment_survives_sudo_reset(self):
        for version in ("", "v1.294.0"):
            for existing in (False, True):
                with self.subTest(version=version, existing=existing), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    bin_dir = root / "bin"
                    install_dir = root / "custom install"
                    bin_dir.mkdir()
                    install_dir.mkdir()
                    if existing:
                        old_cli = install_dir / "ryvn"
                        old_cli.write_text('#!/bin/bash\nprintf "old\\n"\n')
                        old_cli.chmod(0o755)
                    scripts = {
                        "sudo": '''#!/bin/bash
if [[ "${1:-}" == "-E" ]]; then shift; fi
exec env -i PATH="$PATH" HOME="$HOME" "$@"
''',
                        "curl": '''#!/bin/bash
cat <<'INSTALLER'
set -eu
mkdir -p "${INSTALL_DIR:-$HOME/fallback}"
printf '#!/bin/bash\\nprintf "%%s\\n" "%s"\\n' "${RYVN_CLI_VERSION:-latest}" > "${INSTALL_DIR:-$HOME/fallback}/ryvn"
chmod +x "${INSTALL_DIR:-$HOME/fallback}/ryvn"
INSTALLER
''',
                    }
                    for name, script in scripts.items():
                        path = bin_dir / name
                        path.write_text(script)
                        path.chmod(0o755)
                    env = {
                        "HOME": tmp,
                        "PATH": f"{bin_dir}:{install_dir}:/usr/bin:/bin",
                        "RUNNER_OS": "Linux",
                        "RYVN_CLI_VERSION": version,
                    }
                    for name, value in ACTION["runs"]["steps"][0].get("env", {}).items():
                        env[name] = value.replace(
                            "${{ inputs.install-dir }}", str(install_dir)
                        )
                    # Execute the composite action's script, not a copy of its command.
                    script = ACTION["runs"]["steps"][0]["run"].replace(
                        "${{ inputs.install-dir }}", str(install_dir)
                    )
                    subprocess.run(["bash", "-eo", "pipefail", "-c", script], env=env, check=True)
                    result = subprocess.check_output([str(install_dir / "ryvn")], text=True)
                    self.assertEqual(result.strip(), version or "latest")
                    self.assertFalse((root / "fallback").exists())


if __name__ == "__main__":
    unittest.main()
