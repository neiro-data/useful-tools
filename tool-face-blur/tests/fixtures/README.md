# Test fixtures

- `face.jpg` - 330x412 crop/downscale of "Neil Armstrong pose.jpg" (NASA Photo ID S69-31741,
  Apollo 11 crew portrait). Public domain (work of NASA, 17 U.S.C. 105).
  Source: https://commons.wikimedia.org/wiki/File:Neil_Armstrong_pose.jpg
  (original: https://www.nasa.gov/images/content/464436main_S69-31741_full.jpg).
  Re-encoded with Pillow (JPEG q85, no metadata).
- `face_rotated.jpg` - same image with pixels stored rotated 90 degrees CCW and EXIF
  Orientation=6, so a correct decoder yields the upright 330x412 image (stored dims 412x330).
