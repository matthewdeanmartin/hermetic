# # tests/test_guards/test_filesystem.py
# import pytest
# import os
# import builtins
# from hermetic.guards.filesystem import install, uninstall
# from hermetic.errors import PolicyViolation
#
# def test_filesystem_readonly(tmp_file):
#     install(fs_root=str(tmp_file.parent), trace=True)
#     try:
#         with open(tmp_file, "r") as f:
#             assert f.read() == "test content"
#         with pytest.raises(PolicyViolation, match="filesystem readonly"):
#             with open(tmp_file, "w") as f:
#                 f.write("new content")
#         with pytest.raises(PolicyViolation, match="read outside sandbox root"):
#             with open("/tmp/outside.txt", "r"):
#                 pass
#     finally:
#         uninstall()
