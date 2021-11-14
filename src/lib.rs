use pyo3::exceptions::PyException;
use pyo3::prelude::*;

use notify::{RecursiveMode, Result, Watcher};
use std::net::TcpStream;
use std::path::Path;

use std::io::{Read, Write};

pub fn u16_to_array_of_u8(n: u16) -> [u8; 2] {
    let b1 = ((n >> 8) & 0xff) as u8;
    let b2 = (n & 0xff) as u8;
    [b1, b2]
}

pub fn u8_array_to_u16(array: &[u8; 2]) -> u16 {
    ((array[0] as u16) << 8) + (array[1] as u16)
}

pub fn send_str(stream: &mut TcpStream, message: &str) {
    let bytes_arr = message.as_bytes();
    let len = message.len() as u16;
    let size = u16_to_array_of_u8(len);
    stream.write_all(&size).unwrap();
    stream.write_all(bytes_arr).unwrap();
}

pub fn receive_str(stream: &mut TcpStream) -> String {
    let mut size_buffer = [0; 2];
    stream.read_exact(&mut size_buffer).unwrap();
    let mut message_buffer: Vec<u8> = vec![0; u8_array_to_u16(&size_buffer) as usize];
    let _bytes_read = stream.read(&mut message_buffer).unwrap();
    String::from_utf8(message_buffer).expect("Found invalid UTF-8")
}

fn check_for_stop(stream: &mut TcpStream) -> bool {
    receive_str(stream) == "stop"
}

pub fn start_watch(
    mut stream: TcpStream,
    path: &str,
    recursive: bool,
) -> notify::RecommendedWatcher {
    let mut watch = notify::recommended_watcher(move |res| match res {
        Ok(event) => {
            let serialized = serde_json::to_string(&event).unwrap();
            send_str(&mut stream, &serialized);
        }
        Err(e) => panic!("watch error: {:?}", e),
    })
    .unwrap();

    let recursive = match recursive {
        true => RecursiveMode::Recursive,
        false => RecursiveMode::NonRecursive,
    };
    watch.watch(Path::new(path), recursive).unwrap();
    watch
}

pub fn watch_path_rs(address: &str, path: &str, recursive: bool) -> Result<String> {
    // let (sender, receiver): (Sender<String>, Receiver<String>) = channel();

    let mut stream = TcpStream::connect(&address)?;
    let stream_cpy = stream.try_clone().unwrap();
    let _watch = start_watch(stream_cpy, path, recursive);
    send_str(&mut stream, "ready");
    let mut stop = false;
    while !stop {
        stop = check_for_stop(&mut stream);
    }
    Ok("Rust finished successfully".to_string())
}

#[pyfunction]
pub fn watch_path(address: String, path: String, recursive: bool) -> PyResult<String> {
    println!("Running Rust!");
    // Ok("Done rust".to_string())
    match watch_path_rs(&address, &path, recursive) {
        Ok(message) => Ok(message),
        Err(error) => Err(PyException::new_err(error.to_string())),
    }
}

#[pymodule]
fn watchfs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(watch_path, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use regex::Regex;
    use std::fs::File;
    use std::net::TcpListener;
    use std::thread;
    use tempdir::TempDir;

    const ARR1: [u8; 2] = [0, 5];
    const ARR2: [u8; 2] = [1, 0];
    const ARR3: [u8; 2] = [2, 13];
    const VAL1: u16 = 5;
    const VAL2: u16 = u16::pow(2, 8);
    const VAL3: u16 = u16::pow(2, 9) + 13;

    #[test]
    fn test_u16_to_array_of_u8() {
        assert_eq!(u16_to_array_of_u8(VAL1), ARR1);
        assert_eq!(u16_to_array_of_u8(VAL2), ARR2);
        assert_eq!(u16_to_array_of_u8(VAL3), ARR3);
    }

    #[test]
    fn test_u8_array_to_u16() {
        assert_eq!(u8_array_to_u16(&ARR1), VAL1);
        assert_eq!(u8_array_to_u16(&ARR2), VAL2);
        assert_eq!(u8_array_to_u16(&ARR3), VAL3);
    }

    #[test]
    fn test_send_receive_str() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let mut send_stream = TcpStream::connect(addr).unwrap();
        let test_string = "Test String 123!@#/}^%";
        match listener.accept() {
            Ok((mut receive_stream, _addr)) => {
                send_str(&mut send_stream, test_string);
                assert_eq!(receive_str(&mut receive_stream), test_string);
            }
            Err(error) => panic!("Could not get client for test. Error: {:?}", error),
        }
    }

    #[test]
    fn test_check_for_stop() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let mut send_stream = TcpStream::connect(addr).unwrap();
        match listener.accept() {
            Ok((mut receive_stream, _addr)) => {
                send_str(&mut send_stream, "stop");
                assert!(check_for_stop(&mut receive_stream));
                send_str(&mut send_stream, "not stop");
                assert!(!check_for_stop(&mut receive_stream));
            }
            Err(error) => panic!("Could not get client for test. Error: {:?}", error),
        }
    }

    #[test]
    fn test_watch_path_rs() {
        let dir = TempDir::new("watchfs_rust_tests").unwrap();
        let owned_dir_path = dir.path().to_owned();
        let file_path = dir.path().join("foo.txt");
        let file_path_str = file_path.to_str().unwrap();

        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap().to_string();
        let watch = thread::spawn(move || {
            let path = owned_dir_path.to_str().unwrap();
            watch_path_rs(&addr, path, true).unwrap();
        });

        match listener.accept() {
            Ok((mut stream, _addr)) => {
                let ready = receive_str(&mut stream);
                assert_eq!(ready, "ready");

                let _f = File::create(file_path_str).unwrap();

                let file_change_str = receive_str(&mut stream);
                let re = Regex::new(r#"^\{"type":\{"create":"#).unwrap(); //\{"kind":"(any|file)"\}\},"paths":\[".*"\],"attrs":\{\}\}$"#).unwrap(); //.*"]"$
                assert!(re.is_match(&file_change_str));
                send_str(&mut stream, "stop");
                watch.join().unwrap();
            }
            Err(error) => panic!("Could not get client for test. Error: {:?}", error),
        }
        dir.close().unwrap();
    }
}
