import click
import requests
import shutil
from pathlib import Path
import subprocess
import os


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
    extract_dir = Path("protoc")
    extract_dir.mkdir()
    shutil.unpack_archive(protoc_zip, extract_dir=extract_dir)

    # Run
    bin_path = extract_dir / "bin"
    os.chdir(bin_path)
    subprocess.run(
        [
            "protoc",
            f"-I={str(this_dir.parent / 'src')}",
            f"--python_out={str(this_dir.parent / 'python' / 'watchfs')}/",
            str(this_dir.parent / "src" / "watchfs.proto"),
        ],
        check=True,
        stdout=subprocess.PIPE,
    )


if __name__ == "__main__":
    run_protoc()
