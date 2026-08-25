USE concurso_benet;

CREATE TABLE IF NOT EXISTS usuarios_admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(80) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    password_hash CHAR(64) NOT NULL,
    rol ENUM('ADMIN','LABORATORIO') NOT NULL DEFAULT 'ADMIN',
    activo TINYINT(1) NOT NULL DEFAULT 1,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ganadores_concurso (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pdv_id INT NOT NULL,
    foto_id INT NOT NULL,
    posicion TINYINT NOT NULL,
    seleccionado_por INT NOT NULL,
    fecha_seleccion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ganador_pdv (pdv_id),
    UNIQUE KEY uq_ganador_foto (foto_id),
    UNIQUE KEY uq_ganador_posicion (posicion),
    CONSTRAINT chk_posicion_ganador CHECK (posicion BETWEEN 1 AND 5),
    CONSTRAINT fk_ganador_pdv FOREIGN KEY (pdv_id) REFERENCES pdv(id),
    CONSTRAINT fk_ganador_foto FOREIGN KEY (foto_id) REFERENCES fotos(id),
    CONSTRAINT fk_ganador_usuario FOREIGN KEY (seleccionado_por) REFERENCES usuarios_admin(id)
);

INSERT INTO usuarios_admin
(usuario, nombre, password_hash, rol)
VALUES
('16509', 'Administrador Concurso Bénet', 'c3085c8ffc58d45ac1cd99d72d494e2909ad66745ea4d5cb64d3794a16760c4d', 'ADMIN')
ON DUPLICATE KEY UPDATE
nombre = VALUES(nombre),
rol = VALUES(rol),
activo = 1;

INSERT INTO usuarios_admin
(usuario, nombre, password_hash, rol)
VALUES
('Grupo Nutresa', 'Monica Lopez Garcia', '30a5e60713629b7e08b7b4add4900486ca0b1677912da1912ad382c7a1bdff5c', 'LABORATORIO')
ON DUPLICATE KEY UPDATE
nombre = VALUES(nombre),
rol = VALUES(rol),
activo = 1;

SELECT id, usuario, nombre, rol, activo
FROM usuarios_admin;
