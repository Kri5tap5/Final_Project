import tkinter as tk
import requests
import json
import os
from dotenv import load_dotenv
from tkinter.scrolledtext import ScrolledText

load_dotenv()

API_URL = os.getenv('api_url')
THREAD_ID = os.getenv('thread_id')

class ChatApp:
    def __init__(self, root):

        self.root = root
        self.root.title("Desktop Chat App")
        self.root.geometry("635x800")  # Default window size

        # Chat history frame
        self.messages_frame = tk.Frame(self.root, bg="#a5a6a8")
        self.messages_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.messages_canvas = tk.Canvas(self.messages_frame, bg="white")
        self.scrollbar = tk.Scrollbar(self.messages_frame, orient="vertical", command=self.messages_canvas.yview)
        self.scrollable_frame = tk.Frame(self.messages_canvas, bg="light gray")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.messages_canvas.configure(scrollregion=self.messages_canvas.bbox("all"))
        )

        self.messages_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.messages_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.messages_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.messages_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Input frame
        self.input_frame = tk.Frame(self.root)
        self.input_frame.pack(fill=tk.X, padx=10, pady=5)

        self.input_field = tk.Entry(self.input_frame, width=50, font=("Arial", 12))
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_field.bind("<Return>", self.send_message_with_event)  # Bind "Enter" key

        self.send_button = tk.Button(self.input_frame, text="Send", command=self.send_message, bg="#007BFF", fg="white")
        self.send_button.pack(side=tk.RIGHT)

        # Populate chat history
        self.populate_chat()
        #self.root.bind("<Configure>", self._on_resize)
        #For some reason this crashes the app on startup :/

    def _on_resize(self, event):
        """Handle window resizing to adjust message bubble sizes."""
        self.messages_canvas.itemconfig(
            self.messages_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw"),
            width=event.width - 40  # Subtract padding to fit the window
        )

    def _on_mousewheel(self, event):
        """Scroll the chat history with the mouse wheel."""
        self.messages_canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def add_message(self, message, sender):
        """Add a message bubble to the chat window."""
        bubble_frame = tk.Frame(self.scrollable_frame, bg="white", pady=5)

        # Configure alignment and colors based on the sender
        if sender == "user":
            msg_label = tk.Label(
                bubble_frame, text=message, bg="#d4f8e8", fg="#000", wraplength=self.root.winfo_width() - 120,
                justify="left", anchor="e", padx=10, pady=5, font=("Arial", 12)
            )
            msg_label.pack(anchor="e", side = tk.RIGHT, fill="x", padx=10)
        else:  # assistant
            msg_label = tk.Label(
                bubble_frame, text=message, bg="#d4e6f1", fg="#000", wraplength=self.root.winfo_width() - 120,
                justify="left", anchor="w", padx=10, pady=5, font=("Arial", 12)
            )
            msg_label.pack(anchor="w", side = tk.LEFT, fill="x", padx=10)

        bubble_frame.pack(fill="x", padx=5, pady=2)
        self.messages_canvas.update_idletasks()
        self.messages_canvas.yview_moveto(1.0)  # Auto-scroll to the bottom

    def populate_chat(self):
        """Fetches conversation history and displays it."""
        try:
            response = requests.get(f"{API_URL}/conversation-history/?thread_id={THREAD_ID}")
            if response.status_code == 200:
                data = response.json()
                for message in data['conversation_history']:
                    self.add_message(message['content'], message['role'])
        except Exception as e:
            print(f"Error fetching conversation history: {e}")

    def send_message(self):
        """Sends a new message and updates the chat."""
        user_message = self.input_field.get()
        if user_message.strip():
            self.add_message(user_message, "user")
            self.input_field.delete(0, tk.END)

            try:
                response = requests.post(f"{API_URL}/send-message/?thread_id={THREAD_ID}&message={user_message}")
                if response.status_code == 200:
                    assistant_response = response.json()["response"]
                    self.add_message(assistant_response, "assistant")
                else:
                    self.add_message("Error: Unable to get a response from the server.", "assistant")
            except Exception as e:
                self.add_message(f"Error: {e}", "assistant")

    def send_message_with_event(self, event):
        """Wrapper to handle sending message when 'Enter' key is pressed."""
        self.send_message()

if __name__ == "__main__":
    root = tk.Tk()
    chat_app = ChatApp(root)
    root.mainloop()
