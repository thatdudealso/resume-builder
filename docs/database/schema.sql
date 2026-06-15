--
-- PostgreSQL database dump
--

\restrict ResumeBuilderSchema

-- Dumped from database version 16.10 (Homebrew)
-- Dumped by pg_dump version 16.10 (Homebrew)

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_run_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_run_events (
    id bigint NOT NULL,
    run_id uuid,
    node_name character varying(50) NOT NULL,
    event_type character varying(30) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: agent_run_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agent_run_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agent_run_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agent_run_events_id_seq OWNED BY public.agent_run_events.id;


--
-- Name: agent_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_runs (
    id uuid NOT NULL,
    user_id uuid,
    master_resume_id uuid,
    jd_text text NOT NULL,
    status character varying(20) DEFAULT 'queued'::character varying,
    is_free_trial_run boolean DEFAULT false,
    output_locked boolean DEFAULT false,
    payment_id uuid,
    ats_score_before numeric(5,2),
    ats_score_after numeric(5,2),
    final_output jsonb,
    preview_text character varying(500),
    error_message text,
    total_cost_usd numeric(10,4),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: crypto_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_payments (
    id uuid NOT NULL,
    payment_id uuid,
    pay_currency character varying(20) NOT NULL,
    pay_amount numeric(20,8) NOT NULL,
    pay_address character varying(255),
    tx_hash character varying(255),
    confirmations integer DEFAULT 0,
    webhook_payload jsonb
);


--
-- Name: crypto_webhook_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_webhook_events (
    id uuid NOT NULL,
    provider_event_id character varying(255) NOT NULL,
    payment_id uuid,
    event_type character varying(50) NOT NULL,
    payload jsonb NOT NULL,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: device_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_sessions (
    id uuid NOT NULL,
    user_id uuid,
    device_fingerprint character varying(64) NOT NULL,
    ip_hash character varying(64) NOT NULL,
    user_agent character varying(512),
    first_seen_at timestamp with time zone DEFAULT now(),
    last_seen_at timestamp with time zone DEFAULT now()
);


--
-- Name: exports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exports (
    id uuid NOT NULL,
    user_id uuid,
    run_id uuid,
    format character varying(10) NOT NULL,
    s3_key character varying(512) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: master_resumes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.master_resumes (
    id uuid NOT NULL,
    user_id uuid,
    filename character varying(255) NOT NULL,
    s3_key character varying(512) NOT NULL,
    raw_text text NOT NULL,
    structured_json jsonb,
    is_free_trial_resume boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    id uuid NOT NULL,
    user_id uuid,
    run_id uuid,
    provider character varying(20) NOT NULL,
    provider_payment_id character varying(255) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    amount_usd numeric(10,2) NOT NULL,
    currency character varying(10) DEFAULT 'USD'::character varying,
    status character varying(20) DEFAULT 'pending'::character varying,
    unlocks_uploads boolean DEFAULT false,
    metadata jsonb,
    confirmed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id uuid NOT NULL,
    user_id uuid,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: stripe_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stripe_events (
    id uuid NOT NULL,
    stripe_event_id character varying(255) NOT NULL,
    event_type character varying(100) NOT NULL,
    payload jsonb NOT NULL,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    is_active boolean DEFAULT true,
    free_trial_used boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: agent_run_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_run_events ALTER COLUMN id SET DEFAULT nextval('public.agent_run_events_id_seq'::regclass);


--
-- Name: agent_run_events agent_run_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_run_events
    ADD CONSTRAINT agent_run_events_pkey PRIMARY KEY (id);


--
-- Name: agent_runs agent_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: crypto_payments crypto_payments_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_payments
    ADD CONSTRAINT crypto_payments_payment_id_key UNIQUE (payment_id);


--
-- Name: crypto_payments crypto_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_payments
    ADD CONSTRAINT crypto_payments_pkey PRIMARY KEY (id);


--
-- Name: crypto_webhook_events crypto_webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_webhook_events
    ADD CONSTRAINT crypto_webhook_events_pkey PRIMARY KEY (id);


--
-- Name: crypto_webhook_events crypto_webhook_events_provider_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_webhook_events
    ADD CONSTRAINT crypto_webhook_events_provider_event_id_key UNIQUE (provider_event_id);


--
-- Name: device_sessions device_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_sessions
    ADD CONSTRAINT device_sessions_pkey PRIMARY KEY (id);


--
-- Name: exports exports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_pkey PRIMARY KEY (id);


--
-- Name: master_resumes master_resumes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_resumes
    ADD CONSTRAINT master_resumes_pkey PRIMARY KEY (id);


--
-- Name: payments payments_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: payments payments_provider_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_provider_payment_id_key UNIQUE (provider_payment_id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: stripe_events stripe_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_events
    ADD CONSTRAINT stripe_events_pkey PRIMARY KEY (id);


--
-- Name: stripe_events stripe_events_stripe_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stripe_events
    ADD CONSTRAINT stripe_events_stripe_event_id_key UNIQUE (stripe_event_id);


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
-- Name: ix_agent_run_events_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_run_events_run_id ON public.agent_run_events USING btree (run_id);


--
-- Name: ix_agent_runs_output_locked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_runs_output_locked ON public.agent_runs USING btree (output_locked);


--
-- Name: ix_agent_runs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_agent_runs_user_id ON public.agent_runs USING btree (user_id);


--
-- Name: ix_device_sessions_ip_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_sessions_ip_hash ON public.device_sessions USING btree (ip_hash);


--
-- Name: ix_exports_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exports_user_id ON public.exports USING btree (user_id);


--
-- Name: ix_master_resumes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_master_resumes_user_id ON public.master_resumes USING btree (user_id);


--
-- Name: ix_payments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payments_user_id ON public.payments USING btree (user_id);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: agent_run_events agent_run_events_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_run_events
    ADD CONSTRAINT agent_run_events_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.agent_runs(id) ON DELETE CASCADE;


--
-- Name: agent_runs agent_runs_master_resume_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_master_resume_id_fkey FOREIGN KEY (master_resume_id) REFERENCES public.master_resumes(id);


--
-- Name: agent_runs agent_runs_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: agent_runs agent_runs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: crypto_payments crypto_payments_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_payments
    ADD CONSTRAINT crypto_payments_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: crypto_webhook_events crypto_webhook_events_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_webhook_events
    ADD CONSTRAINT crypto_webhook_events_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id);


--
-- Name: device_sessions device_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_sessions
    ADD CONSTRAINT device_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: exports exports_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.agent_runs(id);


--
-- Name: exports exports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exports
    ADD CONSTRAINT exports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payments fk_payments_run_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_run_id FOREIGN KEY (run_id) REFERENCES public.agent_runs(id);


--
-- Name: master_resumes master_resumes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_resumes
    ADD CONSTRAINT master_resumes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payments payments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict ResumeBuilderSchema

