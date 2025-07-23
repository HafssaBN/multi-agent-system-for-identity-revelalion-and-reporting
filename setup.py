import setuptools

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

__version__ = "0.0.0"
REPO_NAME = "multi-agent-system-for-identity-revelalion-and-reporting"
AUTHOR_USER_NAME = ["HafssaBN", "mohamed-stifi"]
PROJECT_NAME = "multi_agents"

setuptools.setup(
    name=PROJECT_NAME,
    version=__version__,
    author=AUTHOR_USER_NAME,
    description="A simple python package for our .",
    long_description=long_description,
    long_description_content="text/markdown",
    project_urls={
        "Bug Tracker": f"https://github.com/{AUTHOR_USER_NAME[0]}/{REPO_NAME}/issues",
    },
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
)