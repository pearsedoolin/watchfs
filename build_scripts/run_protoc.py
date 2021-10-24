import click
import requests
import shutil
from pathlib import Path
import subprocess
import os
import stat


@click.command()
@click.option("--url", prompt="Download url", help="The url to download from.")
def run_protoc(url):
    this_dir = Path(__file__).parent.resolve()
    os.chdir(this_dir)

    # Download
    response = requests.get(url)
    protoc_zip = Path("protoc.zip")
    with protoc_zip.open("wb") as file_handle:
        file_handle.write(response.content)

    # Extract
    extract_dir = Path("protoc").resolve()
    extract_dir.mkdir()
    shutil.unpack_archive(protoc_zip, extract_dir=extract_dir)

    # Run
    bin_path = extract_dir / "bin"
    for executable in bin_path.glob("protoc*"):
        os.chmod(executable, executable.stat().st_mode | stat.S_IEXEC)
    proc = subprocess.Popen(
        [
            str(bin_path / "protoc"),
            f"-I={str(this_dir.parent / 'src')}",
            f"--python_out={str(this_dir.parent / 'python' / 'watchfs')}/",
            str(this_dir.parent / "src" / "watchfs.proto"),
        ],
        cwd=bin_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise Exception(f"protoc failed. stdout: {stdout=}  stderr: {stderr}")


if __name__ == "__main__":
    run_protoc()
