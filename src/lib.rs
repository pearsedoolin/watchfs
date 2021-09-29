use pyo3::prelude::*;
use std::net::TcpStream;
use std::{thread, time};
use std::path::{Path, PathBuf};

use prost::Message;

pub mod protobuf {
    include!(concat!(env!("OUT_DIR"), "\\watchfs.protobuf.rs"));
}
use protobuf::{file_change, FileChange, NotifyCommand};
use std::io::Write;

fn u16_to_array_of_u8(n: u16) -> [u8; 2] {
    let b1 = ((n >> 8) & 0xff) as u8;
    let b2 = (n & 0xff) as u8;
    return [b1, b2];
}


fn send_file_change(stream: &mut TcpStream, file_change: &FileChange) {
    // log::info!("Sending file change");
    let mut bytes = Vec::new();
    bytes.reserve(file_change.encoded_len());
    file_change.encode(&mut bytes).unwrap();

    let size = u16_to_array_of_u8(bytes.len() as u16);
    stream.write(&size).unwrap();
    stream.write(&bytes).unwrap();
}


/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String) -> PyResult<String> {
    let mut stream = TcpStream::connect(&address)?;
    let message = format!("opened {}", address);
    let one_sec = time::Duration::from_secs(1);

    let mut file_change = FileChange::default();
    file_change.action = file_change::Action::Create as i32;
    file_change.path = "/here/is/a/path".to_string();

    for _ in 1..3 {
        thread::sleep(one_sec);
        send_file_change(&mut stream, &file_change);
    }
    Ok(message)
}

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
fn watchfs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(watch_path, m)?)?;

    Ok(())
}