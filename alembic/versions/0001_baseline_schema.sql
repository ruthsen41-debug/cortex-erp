--
-- PostgreSQL database dump
--

-- Dumped from database version 16.2
-- Dumped by pg_dump version 16.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: round(double precision, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.round(double precision, integer) RETURNS double precision
    LANGUAGE sql IMMUTABLE
    AS $_$SELECT round($1::numeric, $2)::double precision$_$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_keys (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    api_key text NOT NULL,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    user_id integer,
    action text NOT NULL,
    entity text NOT NULL,
    entity_id integer,
    old_data text,
    new_data text,
    ip_address text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: bank_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_accounts (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    bank_code text DEFAULT '000'::text,
    bank_name text NOT NULL,
    agency text DEFAULT ''::text,
    account_number text DEFAULT ''::text,
    account_type text DEFAULT 'corrente'::text,
    initial_balance double precision DEFAULT 0.0,
    current_balance double precision DEFAULT 0.0,
    color text DEFAULT '#2563eb'::text,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: bank_accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bank_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bank_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bank_accounts_id_seq OWNED BY public.bank_accounts.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    type text NOT NULL,
    dre_group text NOT NULL,
    keywords text DEFAULT ''::text,
    company_id integer DEFAULT 1
);


--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: collection_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collection_logs (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    entry_id integer NOT NULL,
    contact_id integer,
    channel text NOT NULL,
    recipient text NOT NULL,
    message_sent text NOT NULL,
    status text DEFAULT 'enviado'::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: collection_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.collection_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: collection_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.collection_logs_id_seq OWNED BY public.collection_logs.id;


--
-- Name: collection_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collection_rules (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    trigger_days integer NOT NULL,
    channel text NOT NULL,
    message_template text NOT NULL,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: collection_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.collection_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: collection_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.collection_rules_id_seq OWNED BY public.collection_rules.id;


--
-- Name: companies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.companies (
    id integer NOT NULL,
    razao_social text NOT NULL,
    nome_fantasia text NOT NULL,
    cnpj text NOT NULL,
    inscricao_estadual text DEFAULT ''::text,
    inscricao_municipal text DEFAULT ''::text,
    regime_tributario text DEFAULT 'simples_nacional'::text,
    cnae_principal text DEFAULT '6201-5/01'::text,
    aliquota_simples double precision DEFAULT 6.0,
    cep text DEFAULT ''::text,
    logradouro text DEFAULT ''::text,
    numero text DEFAULT ''::text,
    complemento text DEFAULT ''::text,
    bairro text DEFAULT ''::text,
    cidade text DEFAULT 'Cáceres'::text,
    uf text DEFAULT 'MT'::text,
    codigo_ibge_uf text DEFAULT '51'::text,
    codigo_ibge_municipio text DEFAULT '5102504'::text,
    telefone text DEFAULT ''::text,
    email text DEFAULT ''::text,
    chave_pix text DEFAULT ''::text,
    ambiente_fiscal text DEFAULT 'homologacao'::text,
    motor_fiscal text DEFAULT 'sefaz_direto'::text,
    api_fiscal_token text DEFAULT ''::text,
    serie_nfe integer DEFAULT 1,
    proximo_numero_nfe integer DEFAULT 101,
    serie_nfce integer DEFAULT 1,
    proximo_numero_nfce integer DEFAULT 501,
    serie_nfse integer DEFAULT 1,
    proximo_numero_nfse integer DEFAULT 201,
    csc_id text DEFAULT '000001'::text,
    csc_token text DEFAULT 'CORTEX-ERP-CSC-HOMOLOGACAO'::text,
    certificado_nome text DEFAULT ''::text,
    certificado_validade text DEFAULT ''::text,
    certificado_titular text DEFAULT ''::text,
    certificado_b64 text DEFAULT ''::text,
    certificado_senha text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    accountant_token text,
    accountant_email text DEFAULT ''::text
);


--
-- Name: companies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.companies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: companies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.companies_id_seq OWNED BY public.companies.id;


--
-- Name: contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contacts (
    id integer NOT NULL,
    type text DEFAULT 'cliente'::text,
    person_type text DEFAULT 'PJ'::text,
    name text NOT NULL,
    trade_name text DEFAULT ''::text,
    document text DEFAULT ''::text,
    ie_indicator text DEFAULT '9'::text,
    state_registration text DEFAULT ''::text,
    municipal_registration text DEFAULT ''::text,
    email text DEFAULT ''::text,
    phone text DEFAULT ''::text,
    whatsapp text DEFAULT ''::text,
    cep text DEFAULT ''::text,
    street text DEFAULT ''::text,
    number text DEFAULT ''::text,
    complement text DEFAULT ''::text,
    neighborhood text DEFAULT ''::text,
    city text DEFAULT ''::text,
    state text DEFAULT ''::text,
    ibge_code text DEFAULT '5102504'::text,
    credit_limit double precision DEFAULT 0.0,
    notes text DEFAULT ''::text,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1
);


--
-- Name: contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contacts_id_seq OWNED BY public.contacts.id;


--
-- Name: cost_centers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cost_centers (
    id integer NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    monthly_budget double precision DEFAULT 0.0,
    active integer DEFAULT 1,
    company_id integer DEFAULT 1
);


--
-- Name: cost_centers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cost_centers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cost_centers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cost_centers_id_seq OWNED BY public.cost_centers.id;


--
-- Name: crm_deals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crm_deals (
    id integer NOT NULL,
    title text NOT NULL,
    contact_id integer,
    contact_name text DEFAULT ''::text,
    stage text DEFAULT 'prospeccao'::text,
    estimated_value double precision DEFAULT 0.0,
    probability integer DEFAULT 50,
    expected_close_date text DEFAULT ''::text,
    responsible text DEFAULT 'Consultor Comercial'::text,
    temperature text DEFAULT 'morno'::text,
    notes text DEFAULT ''::text,
    converted_sale_id integer,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1
);


--
-- Name: crm_deals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crm_deals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crm_deals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crm_deals_id_seq OWNED BY public.crm_deals.id;


--
-- Name: financial_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_entries (
    id integer NOT NULL,
    type text NOT NULL,
    description text NOT NULL,
    contact_id integer,
    category_id integer,
    cost_center_id integer,
    bank_account_id integer,
    payment_method text DEFAULT 'Pix'::text,
    competence_date text NOT NULL,
    due_date text NOT NULL,
    amount double precision NOT NULL,
    interest double precision DEFAULT 0.0,
    fine double precision DEFAULT 0.0,
    discount double precision DEFAULT 0.0,
    paid_amount double precision DEFAULT 0.0,
    status text DEFAULT 'pendente'::text,
    installment_number integer DEFAULT 1,
    installment_total integer DEFAULT 1,
    group_uid text DEFAULT ''::text,
    recurrence text DEFAULT 'unico'::text,
    document_number text DEFAULT ''::text,
    barcode text DEFAULT ''::text,
    origin_type text DEFAULT 'manual'::text,
    origin_id integer,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1
);


--
-- Name: financial_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_entries_id_seq OWNED BY public.financial_entries.id;


--
-- Name: financial_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_payments (
    id integer NOT NULL,
    entry_id integer NOT NULL,
    bank_account_id integer NOT NULL,
    payment_date text NOT NULL,
    principal_paid double precision NOT NULL,
    interest_paid double precision DEFAULT 0.0,
    fine_paid double precision DEFAULT 0.0,
    discount_applied double precision DEFAULT 0.0,
    total_cash_flow double precision NOT NULL,
    payment_method text DEFAULT 'Pix'::text,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: financial_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_payments_id_seq OWNED BY public.financial_payments.id;


--
-- Name: fiscal_inutilizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fiscal_inutilizations (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    model text NOT NULL,
    series integer NOT NULL,
    start_number integer NOT NULL,
    end_number integer NOT NULL,
    protocol text DEFAULT ''::text,
    reason text NOT NULL,
    status text DEFAULT 'homologado'::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: fiscal_inutilizations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fiscal_inutilizations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fiscal_inutilizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fiscal_inutilizations_id_seq OWNED BY public.fiscal_inutilizations.id;


--
-- Name: fiscal_manifestations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fiscal_manifestations (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    access_key text NOT NULL,
    event_type text NOT NULL,
    protocol text DEFAULT ''::text,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: fiscal_manifestations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fiscal_manifestations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fiscal_manifestations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fiscal_manifestations_id_seq OWNED BY public.fiscal_manifestations.id;


--
-- Name: invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoices (
    id integer NOT NULL,
    model text NOT NULL,
    series integer DEFAULT 1,
    number integer NOT NULL,
    access_key text NOT NULL,
    protocol text DEFAULT ''::text,
    status text DEFAULT 'autorizada'::text,
    environment text DEFAULT 'homologacao'::text,
    nature_operation text DEFAULT 'VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS'::text,
    sale_id integer,
    contact_id integer,
    recipient_name text NOT NULL,
    recipient_doc text NOT NULL,
    recipient_uf text DEFAULT 'MT'::text,
    total_products double precision DEFAULT 0.0,
    total_discounts double precision DEFAULT 0.0,
    total_shipping double precision DEFAULT 0.0,
    total_icms double precision DEFAULT 0.0,
    total_pis double precision DEFAULT 0.0,
    total_cofins double precision DEFAULT 0.0,
    total_iss double precision DEFAULT 0.0,
    total_invoice double precision NOT NULL,
    items_json text DEFAULT '[]'::text,
    xml_content text DEFAULT ''::text,
    correction_letter text DEFAULT ''::text,
    cancel_reason text DEFAULT ''::text,
    issued_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1,
    cce_protocol text DEFAULT ''::text,
    cancel_protocol text DEFAULT ''::text
);


--
-- Name: invoices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoices_id_seq OWNED BY public.invoices.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    user_id integer,
    title text NOT NULL,
    message text NOT NULL,
    type text DEFAULT 'info'::text,
    is_read integer DEFAULT 0,
    link text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: ofx_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ofx_transactions (
    id integer NOT NULL,
    bank_account_id integer NOT NULL,
    fitid text NOT NULL,
    posted_date text NOT NULL,
    amount double precision NOT NULL,
    memo text NOT NULL,
    suggested_category_id integer,
    matched_entry_id integer,
    status text DEFAULT 'pendente'::text,
    reconciled_at text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1
);


--
-- Name: ofx_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ofx_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ofx_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ofx_transactions_id_seq OWNED BY public.ofx_transactions.id;


--
-- Name: payment_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_charges (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    entry_id integer NOT NULL,
    gateway text DEFAULT 'asaas'::text,
    gateway_id text,
    billing_type text NOT NULL,
    status text DEFAULT 'PENDING'::text,
    value double precision NOT NULL,
    net_value double precision,
    due_date text NOT NULL,
    payment_date text,
    pix_copy_paste text,
    pix_qr_code_b64 text,
    bank_slip_url text,
    invoice_url text,
    customer_id text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    updated_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: payment_charges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_charges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_charges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_charges_id_seq OWNED BY public.payment_charges.id;


--
-- Name: price_tables; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.price_tables (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    discount_percent double precision DEFAULT 0.0,
    markup_percent double precision DEFAULT 0.0,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: price_tables_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.price_tables_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: price_tables_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.price_tables_id_seq OWNED BY public.price_tables.id;


--
-- Name: product_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_batches (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    product_id integer NOT NULL,
    warehouse_id integer DEFAULT 1,
    batch_number text NOT NULL,
    expiry_date text,
    manufacturing_date text,
    quantity double precision DEFAULT 0.0,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: product_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_batches_id_seq OWNED BY public.product_batches.id;


--
-- Name: product_variants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_variants (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    product_id integer NOT NULL,
    variant_name text NOT NULL,
    sku text NOT NULL,
    additional_price double precision DEFAULT 0.0,
    stock_qty double precision DEFAULT 0.0,
    active integer DEFAULT 1
);


--
-- Name: product_variants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_variants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_variants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_variants_id_seq OWNED BY public.product_variants.id;


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id integer NOT NULL,
    type text DEFAULT 'produto'::text,
    sku text NOT NULL,
    barcode text DEFAULT ''::text,
    name text NOT NULL,
    category_name text DEFAULT 'Geral'::text,
    unit text DEFAULT 'UN'::text,
    cost_price double precision DEFAULT 0.0,
    average_cost double precision DEFAULT 0.0,
    margin_percent double precision DEFAULT 50.0,
    sale_price double precision DEFAULT 0.0,
    stock_qty double precision DEFAULT 0.0,
    min_stock double precision DEFAULT 5.0,
    ncm text DEFAULT '84713012'::text,
    cest text DEFAULT ''::text,
    origin text DEFAULT '0'::text,
    cfop_internal text DEFAULT '5102'::text,
    cfop_external text DEFAULT '6102'::text,
    csosn_cst text DEFAULT '102'::text,
    icms_rate double precision DEFAULT 0.0,
    pis_cst text DEFAULT '07'::text,
    pis_rate double precision DEFAULT 0.65,
    cofins_cst text DEFAULT '07'::text,
    cofins_rate double precision DEFAULT 3.0,
    ipi_rate double precision DEFAULT 0.0,
    service_code_lc116 text DEFAULT '01.07'::text,
    iss_rate double precision DEFAULT 3.0,
    iss_retained integer DEFAULT 0,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1,
    warehouse_id integer DEFAULT 1
);


--
-- Name: products_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.products_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
-- Name: purchase_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_items (
    id integer NOT NULL,
    order_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity double precision NOT NULL,
    unit_price double precision NOT NULL,
    discount double precision DEFAULT 0.0,
    total_price double precision NOT NULL
);


--
-- Name: purchase_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_items_id_seq OWNED BY public.purchase_order_items.id;


--
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_orders (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    order_number integer NOT NULL,
    supplier_id integer NOT NULL,
    status text DEFAULT 'rascunho'::text,
    expected_delivery_date text,
    subtotal double precision DEFAULT 0.0,
    discount_amount double precision DEFAULT 0.0,
    shipping_amount double precision DEFAULT 0.0,
    total_amount double precision NOT NULL,
    payment_terms text DEFAULT 'Boleto 30 dias'::text,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    received_at text
);


--
-- Name: purchase_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_orders_id_seq OWNED BY public.purchase_orders.id;


--
-- Name: quote_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quote_items (
    id integer NOT NULL,
    quote_id integer NOT NULL,
    product_id integer,
    product_name text NOT NULL,
    sku text DEFAULT ''::text,
    quantity double precision NOT NULL,
    unit text DEFAULT 'UN'::text,
    unit_price double precision NOT NULL,
    discount double precision DEFAULT 0.0,
    total_price double precision NOT NULL,
    notes text DEFAULT ''::text
);


--
-- Name: quote_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quote_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quote_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quote_items_id_seq OWNED BY public.quote_items.id;


--
-- Name: quotes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quotes (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    quote_number integer NOT NULL,
    type text DEFAULT 'orcamento'::text,
    status text DEFAULT 'rascunho'::text,
    contact_id integer,
    seller_id integer,
    valid_until text,
    payment_terms text DEFAULT 'À Vista'::text,
    subtotal double precision DEFAULT 0.0,
    discount_amount double precision DEFAULT 0.0,
    shipping_amount double precision DEFAULT 0.0,
    total_amount double precision DEFAULT 0.0,
    notes text DEFAULT ''::text,
    internal_notes text DEFAULT ''::text,
    sale_id integer,
    invoice_id integer,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: quotes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quotes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quotes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quotes_id_seq OWNED BY public.quotes.id;


--
-- Name: recurring_contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recurring_contracts (
    id integer NOT NULL,
    title text NOT NULL,
    contact_id integer NOT NULL,
    product_id integer,
    monthly_value double precision NOT NULL,
    due_day integer DEFAULT 10,
    payment_method text DEFAULT 'Boleto'::text,
    bank_account_id integer DEFAULT 1,
    category_id integer DEFAULT 1,
    auto_emit_nfse integer DEFAULT 1,
    status text DEFAULT 'ativo'::text,
    last_billed_month text DEFAULT ''::text,
    start_date text NOT NULL,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1,
    inflation_index text DEFAULT 'IPCA'::text,
    last_adjusted_at text,
    adjustment_percent double precision DEFAULT 0.0
);


--
-- Name: recurring_contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recurring_contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recurring_contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recurring_contracts_id_seq OWNED BY public.recurring_contracts.id;


--
-- Name: sale_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sale_items (
    id integer NOT NULL,
    sale_id integer NOT NULL,
    product_id integer,
    product_name text NOT NULL,
    sku text DEFAULT ''::text,
    unit text DEFAULT 'UN'::text,
    quantity double precision NOT NULL,
    unit_price double precision NOT NULL,
    discount double precision DEFAULT 0.0,
    total_price double precision NOT NULL
);


--
-- Name: sale_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sale_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sale_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sale_items_id_seq OWNED BY public.sale_items.id;


--
-- Name: sales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales (
    id integer NOT NULL,
    number integer NOT NULL,
    sale_type text DEFAULT 'venda'::text,
    status text DEFAULT 'aprovada'::text,
    contact_id integer,
    seller_name text DEFAULT 'Consultor Padrão'::text,
    sale_date text NOT NULL,
    valid_until text DEFAULT ''::text,
    subtotal double precision DEFAULT 0.0,
    discount_amount double precision DEFAULT 0.0,
    shipping_amount double precision DEFAULT 0.0,
    total_amount double precision DEFAULT 0.0,
    payment_method text DEFAULT 'Pix'::text,
    installments integer DEFAULT 1,
    bank_account_id integer DEFAULT 1,
    invoice_id integer,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1,
    seller_id integer,
    commission_amount double precision DEFAULT 0.0,
    price_table_id integer,
    token_access text
);


--
-- Name: sales_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_id_seq OWNED BY public.sales.id;


--
-- Name: sales_return_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_return_items (
    id integer NOT NULL,
    return_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity double precision NOT NULL,
    unit_price double precision NOT NULL,
    return_to_stock integer DEFAULT 1
);


--
-- Name: sales_return_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_return_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_return_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_return_items_id_seq OWNED BY public.sales_return_items.id;


--
-- Name: sales_returns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_returns (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    sale_id integer NOT NULL,
    reason text NOT NULL,
    total_returned double precision NOT NULL,
    refund_method text DEFAULT 'credito'::text,
    status text DEFAULT 'concluido'::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: sales_returns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_returns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_returns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_returns_id_seq OWNED BY public.sales_returns.id;


--
-- Name: sellers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sellers (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    email text DEFAULT ''::text,
    phone text DEFAULT ''::text,
    commission_percent double precision DEFAULT 5.0,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: sellers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sellers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sellers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sellers_id_seq OWNED BY public.sellers.id;


--
-- Name: service_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_orders (
    id integer NOT NULL,
    os_number integer NOT NULL,
    contact_id integer,
    equipment text NOT NULL,
    brand_model text DEFAULT ''::text,
    serial_number text DEFAULT ''::text,
    reported_defect text NOT NULL,
    technical_report text DEFAULT ''::text,
    technician text DEFAULT 'Técnico Responsável'::text,
    status text DEFAULT 'aberta'::text,
    priority text DEFAULT 'normal'::text,
    parts_total double precision DEFAULT 0.0,
    labor_total double precision DEFAULT 0.0,
    discount double precision DEFAULT 0.0,
    total_amount double precision DEFAULT 0.0,
    warranty_days integer DEFAULT 90,
    items_json text DEFAULT '[]'::text,
    billed integer DEFAULT 0,
    opened_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    closed_at text,
    company_id integer DEFAULT 1
);


--
-- Name: service_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_orders_id_seq OWNED BY public.service_orders.id;


--
-- Name: stock_movements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_movements (
    id integer NOT NULL,
    product_id integer NOT NULL,
    movement_type text NOT NULL,
    quantity double precision NOT NULL,
    unit_cost double precision DEFAULT 0.0,
    previous_stock double precision DEFAULT 0.0,
    new_stock double precision DEFAULT 0.0,
    reference text DEFAULT ''::text,
    notes text DEFAULT ''::text,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: stock_movements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stock_movements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stock_movements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stock_movements_id_seq OWNED BY public.stock_movements.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    role text DEFAULT 'admin'::text,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: warehouses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.warehouses (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    name text NOT NULL,
    code text NOT NULL,
    location text DEFAULT ''::text,
    is_default integer DEFAULT 0,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: warehouses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.warehouses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: warehouses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.warehouses_id_seq OWNED BY public.warehouses.id;


--
-- Name: webhook_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_deliveries (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    subscription_id integer,
    event_name text NOT NULL,
    payload_json text NOT NULL,
    response_status integer DEFAULT 0,
    success integer DEFAULT 0,
    delivered_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: webhook_deliveries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.webhook_deliveries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhook_deliveries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_deliveries_id_seq OWNED BY public.webhook_deliveries.id;


--
-- Name: webhook_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_subscriptions (
    id integer NOT NULL,
    company_id integer DEFAULT 1,
    target_url text NOT NULL,
    secret text DEFAULT ''::text,
    events text DEFAULT 'all'::text,
    active integer DEFAULT 1,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text)
);


--
-- Name: webhook_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.webhook_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhook_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_subscriptions_id_seq OWNED BY public.webhook_subscriptions.id;


--
-- Name: xml_purchases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.xml_purchases (
    id integer NOT NULL,
    access_key text NOT NULL,
    invoice_number text NOT NULL,
    supplier_cnpj text NOT NULL,
    supplier_name text NOT NULL,
    issue_date text NOT NULL,
    total_amount double precision NOT NULL,
    items_count integer DEFAULT 0,
    installments_count integer DEFAULT 0,
    created_at text DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'::text),
    company_id integer DEFAULT 1
);


--
-- Name: xml_purchases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.xml_purchases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: xml_purchases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.xml_purchases_id_seq OWNED BY public.xml_purchases.id;


--
-- Name: api_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: bank_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts ALTER COLUMN id SET DEFAULT nextval('public.bank_accounts_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: collection_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_logs ALTER COLUMN id SET DEFAULT nextval('public.collection_logs_id_seq'::regclass);


--
-- Name: collection_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_rules ALTER COLUMN id SET DEFAULT nextval('public.collection_rules_id_seq'::regclass);


--
-- Name: companies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies ALTER COLUMN id SET DEFAULT nextval('public.companies_id_seq'::regclass);


--
-- Name: contacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts ALTER COLUMN id SET DEFAULT nextval('public.contacts_id_seq'::regclass);


--
-- Name: cost_centers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cost_centers ALTER COLUMN id SET DEFAULT nextval('public.cost_centers_id_seq'::regclass);


--
-- Name: crm_deals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_deals ALTER COLUMN id SET DEFAULT nextval('public.crm_deals_id_seq'::regclass);


--
-- Name: financial_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries ALTER COLUMN id SET DEFAULT nextval('public.financial_entries_id_seq'::regclass);


--
-- Name: financial_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_payments ALTER COLUMN id SET DEFAULT nextval('public.financial_payments_id_seq'::regclass);


--
-- Name: fiscal_inutilizations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fiscal_inutilizations ALTER COLUMN id SET DEFAULT nextval('public.fiscal_inutilizations_id_seq'::regclass);


--
-- Name: fiscal_manifestations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fiscal_manifestations ALTER COLUMN id SET DEFAULT nextval('public.fiscal_manifestations_id_seq'::regclass);


--
-- Name: invoices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices ALTER COLUMN id SET DEFAULT nextval('public.invoices_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: ofx_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ofx_transactions ALTER COLUMN id SET DEFAULT nextval('public.ofx_transactions_id_seq'::regclass);


--
-- Name: payment_charges id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_charges ALTER COLUMN id SET DEFAULT nextval('public.payment_charges_id_seq'::regclass);


--
-- Name: price_tables id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_tables ALTER COLUMN id SET DEFAULT nextval('public.price_tables_id_seq'::regclass);


--
-- Name: product_batches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_batches ALTER COLUMN id SET DEFAULT nextval('public.product_batches_id_seq'::regclass);


--
-- Name: product_variants id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_variants ALTER COLUMN id SET DEFAULT nextval('public.product_variants_id_seq'::regclass);


--
-- Name: products id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- Name: purchase_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_items_id_seq'::regclass);


--
-- Name: purchase_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders ALTER COLUMN id SET DEFAULT nextval('public.purchase_orders_id_seq'::regclass);


--
-- Name: quote_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quote_items ALTER COLUMN id SET DEFAULT nextval('public.quote_items_id_seq'::regclass);


--
-- Name: quotes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotes ALTER COLUMN id SET DEFAULT nextval('public.quotes_id_seq'::regclass);


--
-- Name: recurring_contracts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_contracts ALTER COLUMN id SET DEFAULT nextval('public.recurring_contracts_id_seq'::regclass);


--
-- Name: sale_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items ALTER COLUMN id SET DEFAULT nextval('public.sale_items_id_seq'::regclass);


--
-- Name: sales id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales ALTER COLUMN id SET DEFAULT nextval('public.sales_id_seq'::regclass);


--
-- Name: sales_return_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_return_items ALTER COLUMN id SET DEFAULT nextval('public.sales_return_items_id_seq'::regclass);


--
-- Name: sales_returns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_returns ALTER COLUMN id SET DEFAULT nextval('public.sales_returns_id_seq'::regclass);


--
-- Name: sellers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sellers ALTER COLUMN id SET DEFAULT nextval('public.sellers_id_seq'::regclass);


--
-- Name: service_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_orders ALTER COLUMN id SET DEFAULT nextval('public.service_orders_id_seq'::regclass);


--
-- Name: stock_movements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements ALTER COLUMN id SET DEFAULT nextval('public.stock_movements_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: warehouses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouses ALTER COLUMN id SET DEFAULT nextval('public.warehouses_id_seq'::regclass);


--
-- Name: webhook_deliveries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_deliveries ALTER COLUMN id SET DEFAULT nextval('public.webhook_deliveries_id_seq'::regclass);


--
-- Name: webhook_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.webhook_subscriptions_id_seq'::regclass);


--
-- Name: xml_purchases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xml_purchases ALTER COLUMN id SET DEFAULT nextval('public.xml_purchases_id_seq'::regclass);


--
-- Name: api_keys api_keys_api_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_api_key_key UNIQUE (api_key);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: bank_accounts bank_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: collection_logs collection_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_logs
    ADD CONSTRAINT collection_logs_pkey PRIMARY KEY (id);


--
-- Name: collection_rules collection_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_rules
    ADD CONSTRAINT collection_rules_pkey PRIMARY KEY (id);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: contacts contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_pkey PRIMARY KEY (id);


--
-- Name: cost_centers cost_centers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cost_centers
    ADD CONSTRAINT cost_centers_pkey PRIMARY KEY (id);


--
-- Name: crm_deals crm_deals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_deals
    ADD CONSTRAINT crm_deals_pkey PRIMARY KEY (id);


--
-- Name: financial_entries financial_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries
    ADD CONSTRAINT financial_entries_pkey PRIMARY KEY (id);


--
-- Name: financial_payments financial_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_payments
    ADD CONSTRAINT financial_payments_pkey PRIMARY KEY (id);


--
-- Name: fiscal_inutilizations fiscal_inutilizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fiscal_inutilizations
    ADD CONSTRAINT fiscal_inutilizations_pkey PRIMARY KEY (id);


--
-- Name: fiscal_manifestations fiscal_manifestations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fiscal_manifestations
    ADD CONSTRAINT fiscal_manifestations_pkey PRIMARY KEY (id);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: ofx_transactions ofx_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ofx_transactions
    ADD CONSTRAINT ofx_transactions_pkey PRIMARY KEY (id);


--
-- Name: payment_charges payment_charges_gateway_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_charges
    ADD CONSTRAINT payment_charges_gateway_id_key UNIQUE (gateway_id);


--
-- Name: payment_charges payment_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_charges
    ADD CONSTRAINT payment_charges_pkey PRIMARY KEY (id);


--
-- Name: price_tables price_tables_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_tables
    ADD CONSTRAINT price_tables_pkey PRIMARY KEY (id);


--
-- Name: product_batches product_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_batches
    ADD CONSTRAINT product_batches_pkey PRIMARY KEY (id);


--
-- Name: product_variants product_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_variants
    ADD CONSTRAINT product_variants_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (id);


--
-- Name: quote_items quote_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quote_items
    ADD CONSTRAINT quote_items_pkey PRIMARY KEY (id);


--
-- Name: quotes quotes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotes
    ADD CONSTRAINT quotes_pkey PRIMARY KEY (id);


--
-- Name: recurring_contracts recurring_contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_contracts
    ADD CONSTRAINT recurring_contracts_pkey PRIMARY KEY (id);


--
-- Name: sale_items sale_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_pkey PRIMARY KEY (id);


--
-- Name: sales sales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_pkey PRIMARY KEY (id);


--
-- Name: sales_return_items sales_return_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_return_items
    ADD CONSTRAINT sales_return_items_pkey PRIMARY KEY (id);


--
-- Name: sales_returns sales_returns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_returns
    ADD CONSTRAINT sales_returns_pkey PRIMARY KEY (id);


--
-- Name: sellers sellers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sellers
    ADD CONSTRAINT sellers_pkey PRIMARY KEY (id);


--
-- Name: service_orders service_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_orders
    ADD CONSTRAINT service_orders_pkey PRIMARY KEY (id);


--
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: warehouses warehouses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_pkey PRIMARY KEY (id);


--
-- Name: webhook_deliveries webhook_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_deliveries
    ADD CONSTRAINT webhook_deliveries_pkey PRIMARY KEY (id);


--
-- Name: webhook_subscriptions webhook_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_subscriptions
    ADD CONSTRAINT webhook_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: xml_purchases xml_purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.xml_purchases
    ADD CONSTRAINT xml_purchases_pkey PRIMARY KEY (id);


--
-- Name: collection_logs collection_logs_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_logs
    ADD CONSTRAINT collection_logs_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.financial_entries(id);


--
-- Name: financial_entries financial_entries_bank_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries
    ADD CONSTRAINT financial_entries_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id) ON DELETE SET NULL;


--
-- Name: financial_entries financial_entries_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries
    ADD CONSTRAINT financial_entries_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE SET NULL;


--
-- Name: financial_entries financial_entries_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries
    ADD CONSTRAINT financial_entries_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id) ON DELETE SET NULL;


--
-- Name: financial_entries financial_entries_cost_center_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_entries
    ADD CONSTRAINT financial_entries_cost_center_id_fkey FOREIGN KEY (cost_center_id) REFERENCES public.cost_centers(id) ON DELETE SET NULL;


--
-- Name: financial_payments financial_payments_bank_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_payments
    ADD CONSTRAINT financial_payments_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id) ON DELETE CASCADE;


--
-- Name: financial_payments financial_payments_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_payments
    ADD CONSTRAINT financial_payments_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.financial_entries(id) ON DELETE CASCADE;


--
-- Name: ofx_transactions ofx_transactions_bank_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ofx_transactions
    ADD CONSTRAINT ofx_transactions_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id) ON DELETE CASCADE;


--
-- Name: payment_charges payment_charges_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_charges
    ADD CONSTRAINT payment_charges_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.financial_entries(id);


--
-- Name: product_batches product_batches_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_batches
    ADD CONSTRAINT product_batches_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: product_variants product_variants_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_variants
    ADD CONSTRAINT product_variants_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: purchase_order_items purchase_order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.purchase_orders(id);


--
-- Name: purchase_order_items purchase_order_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: purchase_orders purchase_orders_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.contacts(id);


--
-- Name: quote_items quote_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quote_items
    ADD CONSTRAINT quote_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: quote_items quote_items_quote_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quote_items
    ADD CONSTRAINT quote_items_quote_id_fkey FOREIGN KEY (quote_id) REFERENCES public.quotes(id) ON DELETE CASCADE;


--
-- Name: quotes quotes_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotes
    ADD CONSTRAINT quotes_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id);


--
-- Name: recurring_contracts recurring_contracts_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_contracts
    ADD CONSTRAINT recurring_contracts_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id) ON DELETE CASCADE;


--
-- Name: sale_items sale_items_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sale_items
    ADD CONSTRAINT sale_items_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id) ON DELETE CASCADE;


--
-- Name: sales sales_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales
    ADD CONSTRAINT sales_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id) ON DELETE SET NULL;


--
-- Name: sales_return_items sales_return_items_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_return_items
    ADD CONSTRAINT sales_return_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: sales_return_items sales_return_items_return_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_return_items
    ADD CONSTRAINT sales_return_items_return_id_fkey FOREIGN KEY (return_id) REFERENCES public.sales_returns(id);


--
-- Name: sales_returns sales_returns_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_returns
    ADD CONSTRAINT sales_returns_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sales(id);


--
-- Name: stock_movements stock_movements_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: users users_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- PostgreSQL database dump complete
--

