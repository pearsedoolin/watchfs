use pyo3::prelude::*;
use pyo3::exceptions::{PyFileNotFoundError, PyValueError};

use std::net::TcpStream;
use std::{thread, time};
use std::sync::mpsc::channel;
use std::path::{Path, PathBuf};
use notify::{Watcher, RecursiveMode, RawEvent, DebouncedEvent, raw_watcher, watcher};

// use std::path::{Path, PathBuf};

use prost::Message;

pub mod protobuf {
    include!(concat!(env!("OUT_DIR"), "/watchfs.protobuf.rs"));
}
use bytes::Bytes;

use std::io::{Write, Read};
use pyo3::ffi::Py_FatalError;

fn u16_to_array_of_u8(n: u16) -> [u8; 2] {
    let b1 = ((n >> 8) & 0xff) as u8;
    let b2 = (n & 0xff) as u8;
    return [b1, b2];
}

fn u8_array_to_u16(array: &[u8; 2]) -> u16 {
    ((array[0] as u16) << 8) + (array[1] as u16)
}


fn send_file_change(stream: &mut TcpStream, debounced_event: &protobuf::DebouncedEvent) {
    // log::info!("Sending file change");
    let mut bytes = Vec::new();
    bytes.reserve(debounced_event.encoded_len());
    debounced_event.encode(&mut bytes).unwrap();

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
                let msg: protobuf::WatchfsCommand = protobuf::WatchfsCommand::decode(&mut bytes_array).unwrap();
                stop = msg.stop;
            },
            _ => panic!("Expected 2 bytes but read {}", bytes_read),
        }
    }
    stop
}

/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String, path: String, recursive: bool) -> PyResult<String> {
    let delay_millis= 100;
    println!("{}, {}, {}, {}",address, path, recursive, delay_millis);
    let mut stream = TcpStream::connect(&address)?;
    stream.set_nonblocking(true).unwrap();
    let mut stop = false;
    let mut debounced_event = protobuf::DebouncedEvent::default();
    let (tx, rx) = channel();

    let recursive = match recursive {
        true => RecursiveMode::Recursive,
        false => RecursiveMode::NonRecursive
    };
    let mut watcher = watcher(tx, time::Duration::from_millis(delay_millis)).unwrap();
    match watcher.watch(path, recursive) {
        Ok(_t) => {
            while stop == false {
                match rx.recv_timeout(time::Duration::from_millis(100)) {
                    Ok(event) => {
                        match event {
                            DebouncedEvent::NoticeWrite(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::NoticeWrite as i32;
                            },
                            DebouncedEvent::NoticeRemove(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::NoticeRemove as i32;
                            },
                            DebouncedEvent::Create(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::Create as i32;
                            },
                            DebouncedEvent::Write(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::Write as i32;
                            },
                            DebouncedEvent::Chmod(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::Chmod as i32;
                            },
                            DebouncedEvent::Remove(path) => {
                                debounced_event.path = Some(path.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::Remove as i32;
                            },
                            DebouncedEvent::Rename(path1, path2) => {
                                debounced_event.path = Some(path1.into_os_string().into_string().unwrap());
                                debounced_event.action = protobuf::debounced_event::Action::Rename as i32;
                            },
                            DebouncedEvent::Rescan => {
                                debounced_event.path = None;
                                debounced_event.action = protobuf::debounced_event::Action::Rescan as i32;
                            },
                            DebouncedEvent::Error(error, path) => {
                                debounced_event.path = match path {
                                    Some(path) => Some(path.into_os_string().into_string().unwrap()),
                                    None => None
                                };
                                debounced_event.error_message = Some(format!("{:?}", error));
                                debounced_event.action = protobuf::debounced_event::Action::Error as i32;
                            },
                            _ => panic!("Unknown event")
                        }
                        send_file_change(&mut stream, &debounced_event);
                    }
                    Err(_e) => (),
                }
                stop = check_for_stop(&mut stream);
            }
            Ok("Rust finished successfully".to_string())
        },
        Err(error) => {
            match error {
                notify::Error::PathNotFound => Err(PyFileNotFoundError::new_err(format!("{}", error))),
                _ => Err(PyValueError::new_err(format!("{}", error)))
            }

        }
    }
}

/// A Python module implemented in Rust. The name of this function must match
/// the `lib.name` setting in the `Cargo.toml`, else Python will not be able to
/// import the module.
///
#[pymodule]
fn watchfs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(watch_path, m)?)?;
    Ok(())
}