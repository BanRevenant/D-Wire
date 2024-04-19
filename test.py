import asyncio
import subprocess


async def run_factorio_server():
    # Standardized path to the Factorio executable
    factorio_exe = "Factorio Server\\bin\\x64\\factorio.exe"
    # Standardized path to the save file
    save_file = "Factorio Server\\saves\\JustMap.zip"

    # Full command as a single string to pass to the shell
    command = f'"{factorio_exe}" --start-server "{save_file}"'

    # Create subprocess using the shell
    process = await asyncio.create_subprocess_shell(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print("Factorio server has been started via shell...")

    async def read_output():
        # Continuously read and display output from the server
        while True:
            line = await process.stdout.readline()
            if line:
                print("Server output:", line.decode().strip())
            else:
                break  # Exit loop if no more output

    async def send_commands():
        # Wait for server to initialize before sending commands
        await asyncio.sleep(10)  # Adjust as needed
        save_command = "/save test_save\n"  # Command to save the game
        print(f"Sending command to Factorio server: {save_command.strip()}")
        process.stdin.write(save_command.encode())  # Send command as bytes
        await process.stdin.drain()

        # Allow time for the server to respond
        await asyncio.sleep(30)
        print("Sending /quit command to stop the server...")
        process.stdin.write(b"/quit\n")
        await process.stdin.drain()

    # Run output reading and command sending concurrently
    await asyncio.gather(
        read_output(),
        send_commands()
    )

    # Wait for the subprocess to finish
    await process.wait()
    print("Factorio server has been stopped.")


if __name__ == "__main__":
    asyncio.run(run_factorio_server())
