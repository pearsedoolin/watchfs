use pyo3::prelude::*;
use std::net::TcpStream;
use std::{thread, time};
use std::path::{Path, PathBuf};

use prost::Message;

pub mod protobuf {
    include!(concat!(env!("OUT_DIR"), "\\watchfs.protobuf.rs"));
}
use protobuf::{file_change, FileChange, WatchfsCommand};
use bytes::{Buf, BufMut, BytesMut, Bytes};

use std::io::{Write, Read};
use std::process::Command;

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

/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String) -> PyResult<String> {
    let mut stream = TcpStream::connect(&address)?;
    stream.set_nonblocking(true);
    let message = format!("opened {}", address);
    let one_sec = time::Duration::from_secs(1);
    let mut stop = false;
    let mut file_change = FileChange::default();
    file_change.action = file_change::Action::Create as i32;
    file_change.path = "/here/is/a/path".to_string();

    let mut size_buffer= [0; 2];


    while stop == false {
        thread::sleep(one_sec);
        send_file_change(&mut stream, &file_change);
        let read_result = stream.read(&mut size_buffer);
        if let Ok(bytes_read) = read_result {
            match bytes_read {
                2 => {
                    println!("size_buffer: {:?}", size_buffer);
                    let message_len = u8_array_to_u16(&size_buffer);
                    println!("message_len: {}", message_len);
                    let mut message_buffer: Vec<u8> =vec![0, message_len as u8];
                    println!("message_buffer: {:?}", message_buffer);

                    // message_buffer.reserve(message_len as usize);
                    let mut bytes_read = 0;
                    while bytes_read != 2 {
                        bytes_read = stream.read(&mut message_buffer).unwrap();
                        println!("message_buffer is: {:?}", message_buffer);
                        println!("bytes_read is: {:?}", bytes_read);
                        thread::sleep(one_sec);
                    }
                    println!("b is: {:?}", message_buffer);
                    let mut b = Bytes::from(message_buffer);

                    let msg: WatchfsCommand = WatchfsCommand::decode(&mut b).unwrap();
                    println!("msg: {:?}", msg);
                    stop = msg.stop;
                },
                _ => panic!("read {} bytes. Expected 2", bytes_read),
            }
        }

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