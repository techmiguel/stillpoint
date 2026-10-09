# References

Datasheets and application notes used to design and check rev A. They belong to their
manufacturers and are linked, not copied. What each one was used for is in
[hardware.md](hardware.md#checked-against-the-datasheets).

| Part | Document | Used for |
|---|---|---|
| Infineon BGT60TR13C | [datasheet](https://www.infineon.com/dgdl/Infineon-BGT60TR13C-DataSheet-v02_49-EN.pdf) | ball map, supplies and noise, clock, VAREF, current, TX power |
| Infineon BGT60TR13C shield board | user manual UG091722 ([product page](https://www.infineon.com/cms/en/product/sensor/radar-sensors/radar-sensors-for-iot/60ghz-radar/bgt60tr13c/)) | land pattern (fig. 5c), π filters per domain (§3.3, fig. 6), oscillator and its series resistor (§3.4) |
| Silicon Labs MGM260P | [datasheet](https://www.silabs.com/documents/public/data-sheets/mgm260p-datasheet.pdf) | ordering code, pinout, land pattern, antenna keep-out, current |
| Silicon Labs CP2102N | [datasheet](https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf) | self-powered connection, RSTb, VBUS sense |
| TI SN74AVC4T245 | [datasheet](https://www.ti.com/lit/ds/symlink/sn74avc4t245.pdf) | pinout, DIR/OE, unused inputs |
| TI TPS7A20 | [datasheet](https://www.ti.com/lit/ds/symlink/tps7a20.pdf) | noise, pinout |
| TI TLV757P | [datasheet](https://www.ti.com/lit/ds/symlink/tlv757p.pdf) | WSON-6 land pattern, dropout |
| Kyocera KC2016 | [datasheet](https://media.digikey.com/pdf/Data%20Sheets/AVX%20PDFs/KC2016K80.0000C1GECN.pdf) | 80 MHz, 1.8 V, phase jitter |
| ST USBLC6-2 | [datasheet](https://www.st.com/resource/en/datasheet/usblc6-2.pdf) | pinout |
| G-Switch GT-USB-7051A | [drawing](https://datasheet.lcsc.com/lcsc/2108072030_G-Switch-GT-USB-7051A_C2843970.pdf) | land pattern and height |
| Tag-Connect TC2030 | [drawing](https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf) | footprint |
| Infineon sensor-xensiv-bgt60trxx | [driver (Apache-2.0)](https://github.com/Infineon/sensor-xensiv-bgt60trxx) | firmware port |
