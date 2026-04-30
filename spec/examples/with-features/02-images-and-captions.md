# Working with Images

Every non-fiction book needs figures. ProseDown handles images with standard Markdown syntax.

A plain image (no caption):

![The Sawtooth Mountains at dawn](images/sawtooths.jpg)

A captioned figure (using the title attribute):

![A trail map of the Redfish Lake area](images/trail-map.png "Figure 1: The Redfish Lake trail system, showing the main loop and summit spur")

The title text becomes a `<figcaption>` in the EPUB. The alt text stays as the accessibility description. This means your images are both captioned for readers and described for screen readers — with no extra syntax.

![An author writing at a desk](images/desk.jpg "Figure 2: The plain-text writing setup — just a text editor and a cup of coffee")
