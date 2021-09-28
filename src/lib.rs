use pyo3::prelude::*;
use std::net::TcpStream;
use std::{thread, time};

/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String) -> PyResult<String> {
    let mut stream = TcpStream::connect(&address)?;
    let message = format!("opened {}", address);
    let one_sec = time::Duration::from_secs(1);

    loop {
        thread::sleep(one_sec);
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