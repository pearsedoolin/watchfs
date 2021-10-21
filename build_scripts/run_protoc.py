import click
import requests
import shutil
from pathlib import Path
import subprocess
import os


@click.command()
@click.option("--url", prompt="Download url", help="The url to download from.")
def run_protoc(url):
    print(f"initial wd: {os.getcwd()}")

    this_dir = Path(__file__).parent.resolve()
    os.chdir(this_dir)

    print(f"this_dir wd: {os.getcwd()}")
    # Download
    response = requests.get(url)
    protoc_zip = Path("protoc.zip")
    with protoc_zip.open("wb") as file_handle:
        file_handle.write(response.content)

    print(f"protoc_zip is: {protoc_zip}")
    print(f"protoc_zip exists: {protoc_zip.exists()}")

    # Extract
    extract_dir = Path("protoc").resolve()
    extract_dir.mkdir()
    shutil.unpack_archive(protoc_zip, extract_dir=extract_dir)

    print(f"extract_dir is: {extract_dir}")
    print(f"extract_dir exists: {extract_dir.exists()}")

    print("listing all paths extracted")
    for path in extract_dir.glob("**/*"):
        print(path)

    # Run
    bin_path = extract_dir / "bin"
    print(f"bin_path is: {bin_path}")
    print(f"bin_path exists: {bin_path.exists()}")
    args = [
        "protoc",
        f"-I={str(this_dir.parent / 'src')}",
        f"--python_out={str(this_dir.parent / 'python' / 'watchfs')}/",
        str(this_dir.parent / "src" / "watchfs.proto"),
    ]
    print(f"args are: {args}")

    os.chdir(bin_path)
    print(f"now in bin path: {os.getcwd()}")

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
