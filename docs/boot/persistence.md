# SMTH live persistence

The boot menu has an entry named "SMTH OS (persistence)" and expects a writable partition labelled SMTH-PERSISTENCE.

This setup erases the selected partition. Verify the device path before running it.

    sudo mkfs.ext4 -L SMTH-PERSISTENCE /dev/DEVICE
    sudo mkdir -p /mnt/smth-persistence
    sudo mount /dev/disk/by-label/SMTH-PERSISTENCE /mnt/smth-persistence
    printf '/ union\n' | sudo tee /mnt/smth-persistence/persistence.conf
    sudo umount /mnt/smth-persistence

Boot the persistence entry after the partition is prepared. This configures live-boot's persistence overlay; it is not an installed-system installer and has not yet been validated in QEMU.

Other boot entries:
- Live: normal read-only live session.
- Copy to RAM: uses live-boot's toram option; requires enough memory for the image.
- Safe graphics: adds nomodeset.
- Recovery shell: uses initramfs break=mount for early boot diagnosis.

A guided disk installer, LUKS setup, and installed-system rollback are not implemented.
