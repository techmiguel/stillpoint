// Radomo y carcasa paramétricos (OpenSCAD). Montaje en techo, v1.
//
// Física: a 60,6 GHz, λ0 = 4,95 mm. Una lámina de espesor λ/2 *dentro del
// material* es transparente: t = λ0 / (2·sqrt(εr)). Para PETG/PLA impresos
// εr ≈ 2,6–3,0 a 60 GHz ⇒ t ≈ 1,43–1,53 mm. Como εr real depende del filamento
// y de la impresión, se imprime un cupón escalonado y se elige el espesor que
// maximiza la SNR medida con el kit (fase F4).
//
// Imprimir: PETG o PLA natural (sin carbono ni pigmentos metálicos), relleno
// 100 %, capa 0,1 mm, la ventana del radomo plana sobre la cama.

part = "cupon";          // "cupon" | "carcasa" | "tapa"
eps_r = 2.8;             // permitividad medida del filamento
lambda0 = 4.95;          // mm
t_radome = lambda0 / (2 * sqrt(eps_r));
gap = lambda0;           // distancia antena-radomo: múltiplo de λ0/2 (barrer 2,5 / 5 / 7,5)
pcb_d = 60;              // placa redonda Ø60
pcb_t = 1.6;
wall = 2.0;
h_inner = 14;            // altura útil sobre la placa (lado de componentes)
usb_w = 9.5;
usb_h = 3.6;

echo(str("espesor λ/2 para εr=", eps_r, ": ", t_radome, " mm"));

// Cupón: 8 escalones de 1,2 a 1,9 mm, 20×20 mm cada uno, con su espesor grabado.
module cupon() {
    for (i = [0:7]) {
        t = 1.2 + 0.1 * i;
        translate([i * 22, 0, 0]) difference() {
            cube([20, 20, t]);
            translate([2, 2, t - 0.3]) linear_extrude(0.31)
                text(str(t), size = 4);
        }
    }
}

// Carcasa: cilindro abierto por arriba (techo); la base es el radomo.
module carcasa() {
    r = pcb_d / 2 + 0.4;
    difference() {
        cylinder(r = r + wall, h = t_radome + gap + h_inner, $fn = 128);
        // interior
        translate([0, 0, t_radome]) cylinder(r = r, h = 100, $fn = 128);
        // salida USB-C lateral
        translate([r - 1, -usb_w / 2, t_radome + gap + 2]) cube([wall + 2, usb_w, usb_h]);
        // ventilación lejos del radar
        for (a = [30:60:330]) rotate(a)
            translate([r - 1, -1, t_radome + gap + 8]) cube([wall + 2, 2, 4]);
    }
    // apoyos de la placa: la cara de antenas queda a `gap` del radomo
    for (a = [0, 120, 240]) rotate(a)
        translate([r - 3, -2, t_radome]) cube([3, 4, gap]);
}

// Tapa al techo con dos taladros para tacos.
module tapa() {
    r = pcb_d / 2 + 0.4 + wall;
    difference() {
        cylinder(r = r + 6, h = 2.4, $fn = 128);
        for (x = [-r, r]) translate([x * 0.8, 0, -1]) cylinder(d = 4.2, h = 5, $fn = 32);
        translate([0, 0, 1.2]) cylinder(r = r - wall + 0.2, h = 2, $fn = 128);
    }
}

if (part == "cupon") cupon();
if (part == "carcasa") carcasa();
if (part == "tapa") tapa();
