from reviewer.diff import added_lines, annotate, commentable_lines

PATCH = """@@ -1,3 +1,4 @@
 a
-b
+B
+c
 d
@@ -20,2 +21,3 @@
 x
+y
 z
"""


def test_added_lines():
    assert added_lines(PATCH) == {2, 3, 22}


def test_commentable_includes_context_but_not_removed():
    assert commentable_lines(PATCH) == {1, 2, 3, 4, 21, 22, 23}


def test_annotate_uses_new_file_numbers():
    out = annotate(PATCH)
    assert "    2 + B" in out
    assert "      - b" in out  # removed lines have no number
    assert "   22 + y" in out
