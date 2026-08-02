-- MySQL database dump (DDL only)

CREATE TABLE `plants` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `plant_type` VARCHAR(255) NOT NULL,
    `capacity_mw` DECIMAL(10,2) NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `plants_name_unique` UNIQUE (`name`)
);

-- Table 1: energy production logs
CREATE TABLE `plant_production` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `plant_id` INT NOT NULL,
    `production_mwh` DECIMAL(12,2) NOT NULL,
    `recorded_at` DATETIME NOT NULL,
    FOREIGN KEY (`plant_id`) REFERENCES `plants`(`id`)
);

-- Table 2: maintenance records
CREATE TABLE `plant_maintenance` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `plant_id` INT NOT NULL,
    `maintenance_type` VARCHAR(255) NOT NULL,
    `cost_eur` DECIMAL(12,2),
    `performed_at` DATETIME NOT NULL
);

-- Table 3: emissions tracking
CREATE TABLE `plant_emissions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `plant_id` INT NOT NULL,
    `co2_tons` DECIMAL(12,3) NOT NULL,
    `reported_at` DATETIME NOT NULL
);

-- Foreign key constraints added separately
ALTER TABLE `plant_maintenance`
    ADD CONSTRAINT `fk_maintenance_plant`
    FOREIGN KEY (`plant_id`)
    REFERENCES `plants`(`id`);

ALTER TABLE `plant_emissions`
    ADD CONSTRAINT `fk_emissions_plant`
    FOREIGN KEY (`plant_id`)
    REFERENCES `plants`(`id`);
