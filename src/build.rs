use std::io::Result;
fn main() -> Result<()> {
    prost_build::compile_protos(&["src/watchfs.proto"], &["src/"])?;
    Ok(())
}
