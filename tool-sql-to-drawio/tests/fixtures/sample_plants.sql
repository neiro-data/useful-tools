-- PostgreSQL database dump (DDL only)

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

SET search_path = public;

-- Central table
CREATE TABLE plants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    plant_type TEXT NOT NULL,
    capacity_mw NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT plants_name_unique UNIQUE (name),
    CONSTRAINT plant_type_check CHECK (plant_type IN ('nuclear', 'solar', 'wind', 'hydro', 'waste')),
    CONSTRAINT capacity_positive CHECK (capacity_mw > 0)
);

-- Table 1: energy production logs
CREATE TABLE plant_production (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL,
    production_mwh NUMERIC(12,2) NOT NULL,
    recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT production_positive CHECK (production_mwh >= 0)
);

-- Table 2: maintenance records
CREATE TABLE plant_maintenance (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    cost_eur NUMERIC(12,2),
    performed_at DATE NOT NULL,
    CONSTRAINT cost_non_negative CHECK (cost_eur IS NULL OR cost_eur >= 0)
);

-- Table 3: emissions tracking
CREATE TABLE plant_emissions (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL,
    co2_tons NUMERIC(12,3) NOT NULL,
    reported_at DATE NOT NULL,
    CONSTRAINT emissions_non_negative CHECK (co2_tons >= 0)
);

-- Foreign key constraints added separately (pg_dump style)
ALTER TABLE ONLY plant_production
    ADD CONSTRAINT fk_production_plant
    FOREIGN KEY (plant_id)
    REFERENCES plants(id)
    ON DELETE CASCADE;

ALTER TABLE ONLY plant_maintenance
    ADD CONSTRAINT fk_maintenance_plant
    FOREIGN KEY (plant_id)
    REFERENCES plants(id)
    ON DELETE CASCADE;

ALTER TABLE ONLY plant_emissions
    ADD CONSTRAINT fk_emissions_plant
    FOREIGN KEY (plant_id)
    REFERENCES plants(id)
    ON DELETE CASCADE;

-- Indexes
CREATE INDEX idx_production_plant_id ON plant_production(plant_id);
CREATE INDEX idx_maintenance_plant_id ON plant_maintenance(plant_id);
CREATE INDEX idx_emissions_plant_id ON plant_emissions(plant_id);
