/**
 * Facts the doctors' privacy page states, kept in one place. They describe the live setup, so update
 * them when it changes (Neon dashboard: region, and the restore window under Settings > Storage).
 */

/** Where doctor accounts are stored (Neon project region; read from the database host name). */
export const DOCTOR_DATA_REGION = "AWS US East (Ohio), us-east-2";

/**
 * How long a deleted account can remain in Neon's restore history, in hours. Null until the owner
 * confirms it from the Neon settings; the page then says "a short time (to be confirmed)".
 */
export const RESTORE_WINDOW_HOURS: number | null = null;

/** Contact for doctors (deletion, verification). Empty until the owner gives the project email. */
export const DOCTOR_CONTACT_EMAIL = "";
