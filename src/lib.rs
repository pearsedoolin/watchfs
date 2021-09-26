use pyo3::prelude::*;

/// Formats the sum of two numbers as string.
#[pyfunction]
fn watch_path(address: String) -> PyResult<String> {
    let message = format!("opened {}", address);
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