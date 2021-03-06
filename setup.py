import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="FxBot",
    install_requires=["pymongo",'pandas','requests'],
    version="1.2.1",
    author="Rastislav_Baran",
    author_email="baranrastislav@gmail.com",
    description="Forex bot trading with EURUSD and storing data into mongodb",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={'FxBot': ['Config/*.json']},
    entry_points={'console_scripts':['fxbot = FxBot.fxbot:run', 'fxbot10 = FxBot.fxbot:run10']},
    url="",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
