from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="github-copilot-chat-exporter",
    version="1.1.0",
    author="Terry Pang",
    description="Export GitHub Copilot shared conversations to Markdown with file attachment capture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pandaxbacon/github-copilot-chat-exporter",
    py_modules=["scraper_playwright", "scraper_requests"],
    install_requires=[
        "beautifulsoup4==4.12.3",
        "playwright==1.48.0",
        "requests==2.32.3",
    ],
    entry_points={
        "console_scripts": [
            "copilot-exporter=scraper_playwright:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.9",
)


