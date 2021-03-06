"""
Unit tests for PySpark; additional tests are implemented as doctests in
individual modules.
"""
import os
import shutil
import sys
from tempfile import NamedTemporaryFile
import time
import unittest

from pyspark.context import SparkContext
from pyspark.files import SparkFiles
from pyspark.java_gateway import SPARK_HOME


class PySparkTestCase(unittest.TestCase):

    def setUp(self):
        self._old_sys_path = list(sys.path)
        class_name = self.__class__.__name__
        self.sc = SparkContext('local[4]', class_name , batchSize=2)

    def tearDown(self):
        self.sc.stop()
        sys.path = self._old_sys_path
        # To avoid Akka rebinding to the same port, since it doesn't unbind
        # immediately on shutdown
        self.sc.jvm.System.clearProperty("spark.driver.port")


class TestCheckpoint(PySparkTestCase):

    def setUp(self):
        PySparkTestCase.setUp(self)
        self.checkpointDir = NamedTemporaryFile(delete=False)
        os.unlink(self.checkpointDir.name)
        self.sc.setCheckpointDir(self.checkpointDir.name)

    def tearDown(self):
        PySparkTestCase.tearDown(self)
        shutil.rmtree(self.checkpointDir.name)

    def test_basic_checkpointing(self):
        parCollection = self.sc.parallelize([1, 2, 3, 4])
        flatMappedRDD = parCollection.flatMap(lambda x: range(1, x + 1))

        self.assertFalse(flatMappedRDD.isCheckpointed())
        self.assertIsNone(flatMappedRDD.getCheckpointFile())

        flatMappedRDD.checkpoint()
        result = flatMappedRDD.collect()
        time.sleep(1)  # 1 second
        self.assertTrue(flatMappedRDD.isCheckpointed())
        self.assertEqual(flatMappedRDD.collect(), result)
        self.assertEqual(self.checkpointDir.name,
                         os.path.dirname(flatMappedRDD.getCheckpointFile()))

    def test_checkpoint_and_restore(self):
        parCollection = self.sc.parallelize([1, 2, 3, 4])
        flatMappedRDD = parCollection.flatMap(lambda x: [x])

        self.assertFalse(flatMappedRDD.isCheckpointed())
        self.assertIsNone(flatMappedRDD.getCheckpointFile())

        flatMappedRDD.checkpoint()
        flatMappedRDD.count()  # forces a checkpoint to be computed
        time.sleep(1)  # 1 second

        self.assertIsNotNone(flatMappedRDD.getCheckpointFile())
        recovered = self.sc._checkpointFile(flatMappedRDD.getCheckpointFile())
        self.assertEquals([1, 2, 3, 4], recovered.collect())


class TestAddFile(PySparkTestCase):

    def test_add_py_file(self):
        # To ensure that we're actually testing addPyFile's effects, check that
        # this job fails due to `userlibrary` not being on the Python path:
        def func(x):
            from userlibrary import UserClass
            return UserClass().hello()
        self.assertRaises(Exception,
                          self.sc.parallelize(range(2)).map(func).first)
        # Add the file, so the job should now succeed:
        path = os.path.join(SPARK_HOME, "python/test_support/userlibrary.py")
        self.sc.addPyFile(path)
        res = self.sc.parallelize(range(2)).map(func).first()
        self.assertEqual("Hello World!", res)

    def test_add_file_locally(self):
        path = os.path.join(SPARK_HOME, "python/test_support/hello.txt")
        self.sc.addFile(path)
        download_path = SparkFiles.get("hello.txt")
        self.assertNotEqual(path, download_path)
        with open(download_path) as test_file:
            self.assertEquals("Hello World!\n", test_file.readline())

    def test_add_py_file_locally(self):
        # To ensure that we're actually testing addPyFile's effects, check that
        # this fails due to `userlibrary` not being on the Python path:
        def func():
            from userlibrary import UserClass
        self.assertRaises(ImportError, func)
        path = os.path.join(SPARK_HOME, "python/test_support/userlibrary.py")
        self.sc.addFile(path)
        from userlibrary import UserClass
        self.assertEqual("Hello World!", UserClass().hello())


if __name__ == "__main__":
    unittest.main()
