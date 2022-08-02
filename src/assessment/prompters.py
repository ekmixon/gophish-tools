"""The prompter module."""

# Third-Party Libraries
from prompt_toolkit import prompt

# cisagov Libraries
from util.validate import BlankInputValidator


def main():
    """Return a URL prompt."""
    return prompt(
        "Campaign URL: ", default="domain", validator=BlankInputValidator()
    )
