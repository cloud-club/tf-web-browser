from block_layout import WIDTH, HEIGHT, HSTEP, VSTEP, BlockLayout

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []
