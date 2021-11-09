mod lib;
use lib::{receive_str, send_str, watch_path_rs};
use std::fs::File;
use std::io::Write;
use std::net::TcpListener;
use std::thread;

fn main() {
    let address: &'static str = "127.0.0.1:7365";
    let listener = TcpListener::bind(&address).unwrap();

    println!("Starting watch_and_send!");

    let address_ref = &address;
    let watcher = thread::spawn(|| {
        watch_path_rs(address_ref, ".", true).unwrap();
    });

    match listener.accept() {
        Ok((mut stream, _addr)) => {
            let ready = receive_str(&mut stream);
            println!("ready: {}", ready);

            let mut file = File::create("foo.txt").unwrap();
            file.write_all(b"Hello, world!").unwrap();

            let event1 = receive_str(&mut stream);
            println!("event1 is: {}", event1);

            send_str(&mut stream, "stop");
            println!("waiting for watch to stop");
            watcher.join().unwrap();
        }
        Err(e) => println!("couldn't get client: {:?}", e),
    }
    println!("Done!");
}
