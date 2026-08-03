`timescale 1ns/1ps

module timestamp_normalizer #(
    parameter int TIMESTAMP_WIDTH = 64,
    parameter int DRIFT_WIDTH = 32
) (
    input  logic                                  clk,
    input  logic                                  rst_n,
    input  logic                                  valid_in,
    input  logic [TIMESTAMP_WIDTH-1:0]            unwrapped_timestamp,
    input  logic signed [TIMESTAMP_WIDTH:0]       offset_ns,
    input  logic signed [DRIFT_WIDTH-1:0]         drift_ppb,
    input  logic [TIMESTAMP_WIDTH-1:0]            reference_timestamp,
    output logic                                  valid_out,
    output logic signed [TIMESTAMP_WIDTH:0]       normalized_timestamp,
    output logic                                  overflow
);
    localparam int VALUE_WIDTH = TIMESTAMP_WIDTH + 1;
    localparam int PRODUCT_WIDTH = VALUE_WIDTH + DRIFT_WIDTH;
    localparam logic signed [PRODUCT_WIDTH-1:0] PPB_SCALE = 1_000_000_000;
    localparam logic signed [PRODUCT_WIDTH-1:0] NORMALIZED_MAX = {
        {DRIFT_WIDTH{1'b0}}, 1'b0, {TIMESTAMP_WIDTH{1'b1}}
    };
    localparam logic signed [PRODUCT_WIDTH-1:0] NORMALIZED_MIN = {
        {DRIFT_WIDTH{1'b1}}, 1'b1, {TIMESTAMP_WIDTH{1'b0}}
    };

    logic signed [VALUE_WIDTH-1:0] raw_value;
    logic signed [VALUE_WIDTH-1:0] reference_value;
    logic signed [VALUE_WIDTH-1:0] elapsed_value;
    logic signed [PRODUCT_WIDTH-1:0] elapsed_extended;
    logic signed [PRODUCT_WIDTH-1:0] reference_extended;
    logic signed [PRODUCT_WIDTH-1:0] drift_extended;
    logic signed [PRODUCT_WIDTH-1:0] offset_extended;
    logic signed [PRODUCT_WIDTH-1:0] drift_product;
    logic signed [PRODUCT_WIDTH-1:0] drift_correction;
    logic signed [PRODUCT_WIDTH-1:0] normalized_extended;
    logic signed [VALUE_WIDTH-1:0] normalized_bounded;
    logic normalization_overflow;

    always_comb begin
        raw_value = $signed({1'b0, unwrapped_timestamp});
        reference_value = $signed({1'b0, reference_timestamp});
        elapsed_value = raw_value - reference_value;
        elapsed_extended = $signed({
            {DRIFT_WIDTH{elapsed_value[VALUE_WIDTH-1]}}, elapsed_value
        });
        reference_extended = $signed({
            {DRIFT_WIDTH{reference_value[VALUE_WIDTH-1]}}, reference_value
        });
        drift_extended = $signed({
            {(PRODUCT_WIDTH-DRIFT_WIDTH){drift_ppb[DRIFT_WIDTH-1]}}, drift_ppb
        });
        offset_extended = $signed({
            {DRIFT_WIDTH{offset_ns[VALUE_WIDTH-1]}}, offset_ns
        });
        drift_product = elapsed_extended * drift_extended;
        drift_correction = drift_product / PPB_SCALE;
        normalized_extended = elapsed_extended
            + reference_extended
            - offset_extended
            - drift_correction;
        normalization_overflow = 1'b0;
        if (normalized_extended > NORMALIZED_MAX) begin
            normalized_bounded = NORMALIZED_MAX[VALUE_WIDTH-1:0];
            normalization_overflow = 1'b1;
        end else if (normalized_extended < NORMALIZED_MIN) begin
            normalized_bounded = NORMALIZED_MIN[VALUE_WIDTH-1:0];
            normalization_overflow = 1'b1;
        end else begin
            normalized_bounded = $signed(normalized_extended[VALUE_WIDTH-1:0]);
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            normalized_timestamp <= '0;
            overflow <= 1'b0;
        end else begin
            valid_out <= valid_in;
            overflow <= valid_in && normalization_overflow;
            if (valid_in) begin
                normalized_timestamp <= normalized_bounded;
            end
        end
    end
endmodule
