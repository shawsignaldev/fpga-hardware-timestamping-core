`timescale 1ns/1ps

module tb_timestamp_unwrapper;
    localparam int COUNTER_WIDTH = 8;
    localparam int EPOCH_WIDTH = 4;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic valid_in = 1'b0;
    logic [COUNTER_WIDTH-1:0] raw_timestamp = '0;
    logic valid_out;
    logic [COUNTER_WIDTH+EPOCH_WIDTH-1:0] unwrapped_timestamp;

    timestamp_unwrapper #(
        .COUNTER_WIDTH(COUNTER_WIDTH),
        .EPOCH_WIDTH(EPOCH_WIDTH)
    ) dut (
        .clk,
        .rst_n,
        .valid_in,
        .raw_timestamp,
        .valid_out,
        .unwrapped_timestamp
    );

    always #5 clk = ~clk;

    task automatic send_and_expect(
        input logic [COUNTER_WIDTH-1:0] raw_value,
        input logic [COUNTER_WIDTH+EPOCH_WIDTH-1:0] expected_value
    );
        @(negedge clk);
        valid_in = 1'b1;
        raw_timestamp = raw_value;
        @(posedge clk);
        #1;
        if (!valid_out || unwrapped_timestamp !== expected_value) begin
            $fatal(1, "raw=%0d expected=%0d actual=%0d valid=%0b",
                raw_value, expected_value, unwrapped_timestamp, valid_out);
        end
        @(negedge clk);
        valid_in = 1'b0;
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        send_and_expect(8'd250, 12'd250);
        send_and_expect(8'd255, 12'd255);
        send_and_expect(8'd2, 12'd258);
        send_and_expect(8'd5, 12'd261);
        send_and_expect(8'd254, 12'd254);
        send_and_expect(8'd6, 12'd262);
        send_and_expect(8'd134, 12'd134);

        @(negedge clk);
        rst_n = 1'b0;
        valid_in = 1'b1;
        @(posedge clk);
        #1;
        if (valid_out || unwrapped_timestamp !== '0) begin
            $fatal(1, "reset did not clear unwrapper outputs");
        end
        @(negedge clk);
        rst_n = 1'b1;
        valid_in = 1'b0;
        send_and_expect(8'd9, 12'd9);

        $display("PASS tb_timestamp_unwrapper");
        $finish;
    end
endmodule
