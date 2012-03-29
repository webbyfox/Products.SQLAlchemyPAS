from setuptools import setup, find_packages
import os

version = '1.0.2'

setup(name='Products.SQLAlchemyPAS',
      version=version,
      description="PAS / PlonePAS plugin fetching user data from a relational database",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      author='Laurence Rowe',
      author_email='laurence@lrowe.co.uk',
      url='http://pypi.python.org/pypi/Products.SQLAlchemyPAS',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['Products'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'z3c.saconfig',
          'DateTime>=2.11.2dev',
      ],
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      )
