use pyo3::prelude::*;
use std::net::TcpStream;
use std::{thread, time};
// use std::path::{Path, PathBuf};

use prost::Message;

pub mod protobuf {
    include!(concat!(env!("OUT_DIR"), "\\watchfs.protobuf.rs"));
}
use protobuf::{file_change, FileChange, WatchfsCommand};
use bytes::Bytes;

use std::io::{Write, Read};

fn u16_to_array_of_u8(n: u16) -> [u8; 2] {
    let b1 = ((n >> 8) & 0xff) as u8;
    let b2 = (n & 0xff) as u8;
    return [b1, b2];
}

fn u8_array_to_u16(array: &[u8; 2]) -> u16 {
    ((array[0] as u16) << 8) + (array[1] as u16)
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


fn check_for_stop(stream: &mut TcpStream) -> bool {
    let mut stop = false;
    let mut size_buffer= [0; 2];

    if let Ok(bytes_read) =  stream.read(&mut size_buffer) {
        match bytes_read {
            2 => {
                let mut message_buffer: Vec<u8> =vec![0, u8_array_to_u16(&size_buffer) as u8];
                let _bytes_read = stream.read(&mut message_buffer).unwrap();
                let mut bytes_array = Bytes::from(message_buffer);
                let msg: WatchfsCommand = WatchfsCommand::decode(&mut bytes_array).unwrap();
                stop = msg.stop;
            },
            _ => panic!("Expected 2 bytes but read {}", bytes_read),
        }
    }
    stop
}

/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String) -> PyResult<String> {
    let mut stream = TcpStream::connect(&address)?;
    stream.set_nonblocking(true).unwrap();
    let one_sec = time::Duration::from_secs(1);
    let mut stop = false;
    let mut file_change = FileChange::default();
    file_change.action = file_change::Action::Create as i32;
    file_change.path = "/here/is/a/path".to_string();

    while stop == false {
        thread::sleep(one_sec);
        send_file_change(&mut stream, &file_change);
        stop = check_for_stop(&mut stream);
    }
    Ok("Rust finished successfully".to_string())
}


/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
#[pymodule]
fn watchfs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(watch_path, m)?)?;
    Ok(())
}