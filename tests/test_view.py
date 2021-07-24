from refpapers.view import print_list


def test_print_list_empty():
    # neither should raise an exception
    print_list([])
    print_list([], grouped='tags')
