from textual.app import App
from textual.containers import Container, Vertical
from textual.widgets import Button, Switch, Label, Checkbox, RadioSet, RadioButton

def create_demo_app():
    """
    Creates a demo application showing all possible switch types in Textual
    Returns: App class with all switch demonstrations
    """
    class SwitchDemoApp(App):
        CSS = """
        Screen {
            background: #1f1f1f;
            align: center middle;
        }

        Container {
            width: 40;
            height: auto;
            border: solid white;
            padding: 1;
        }

        Label {
            margin: 1 0;
            text-align: center;
            color: white;
        }

        Switch {
            margin: 1 0;
        }

        Checkbox {
            margin: 1 0;
            padding: 1;
        }

        RadioSet {
            margin: 1 0;
            border: solid grey;
            padding: 1;
        }

        #title {
            text-style: bold;
            color: skyblue;
        }
        """

        def compose(self):
            """Create the layout with all switch types"""
            # Create main container
            with Container():
                # Add title
                yield Label("Available Switch Types in Textual", id="title")
                yield Label("Click or press space to toggle")

                # 1. Built-in Switch widget
                yield Label("1. Basic Switch:")
                yield Switch()

                # 2. Checkbox widget
                yield Label("2. Checkbox:")
                yield Checkbox("Toggle me")

                # 3. Radio buttons
                yield Label("3. Radio Buttons:")
                with RadioSet():
                    yield RadioButton("Option 1")
                    yield RadioButton("Option 2")
                    yield RadioButton("Option 3")

                # 4. Toggle button
                yield Label("4. Toggle Button:")
                yield Button("Toggle", variant="success")

    return SwitchDemoApp

def main():
    """
    Main function to run the demo
    Includes error handling and setup instructions
    """
    try:
        # Create and run the demo app
        app = create_demo_app()()
        app.run()
    except Exception as e:
        # Show helpful error message and setup instructions
        print("Error running the demo:", str(e))
        print("\nSetup Instructions:")
        print("1. Install latest textual:")
        print("   pip install --upgrade textual")
        print("2. Make sure your terminal supports colors")
        print("3. Try running in a different terminal if issues persist")

if __name__ == "__main__":
    main()